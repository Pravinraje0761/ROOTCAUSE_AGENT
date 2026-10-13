import logging
import math
from datetime import datetime
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from backend.app import database
from backend.app.database import PastIncidentRecord
from backend.app.config import settings

logger = logging.getLogger(__name__)

def get_embedding(text: str) -> List[float]:
    """
    Deterministic keyword-feature vector for the text (no external embedding model).

    Each known failure keyword sets one dimension; the vector is L2-normalised so that
    cosine similarity measures keyword overlap between incidents. The 1536 width only
    keeps the stored shape compatible with common embedding sizes.
    """
    text_lower = text.lower()
    
    # Heuristic vector generation for deterministic fallback matches
    # Vector dimensions: [accuracy, latency, error_rate, preprocessing, model, drift, dependency, workers...]
    vector = [0.0] * 1536
    
    # Assign specific index offsets to keywords
    keywords = {
        "accuracy": 0, "drop": 1, "performance": 2, "degradation": 3,
        "latency": 4, "spike": 5, "slow": 6, "seconds": 7,
        "preprocessing": 8, "scale": 9, "normalization": 10, "minmax": 11,
        "model": 12, "version": 13, "skew": 14, "uncalibrated": 15,
        "drift": 16, "distribution": 17, "covariate": 18,
        "dependency": 19, "numpy": 20, "version": 21,
        "workers": 22, "threading": 23, "concurrency": 24
    }
    
    for kw, idx in keywords.items():
        if kw in text_lower:
            vector[idx] = 1.0
            
    # Normalize vector
    sq_sum = sum(x*x for x in vector)
    if sq_sum > 0:
        norm = math.sqrt(sq_sum)
        vector = [x / norm for x in vector]
        
    return vector

def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    if len(v1) != len(v2):
        return 0.0
    dot = sum(a*b for a, b in zip(v1, v2))
    sum1 = sum(a*a for a in v1)
    sum2 = sum(b*b for b in v2)
    if sum1 == 0 or sum2 == 0:
        return 0.0
    return dot / (math.sqrt(sum1) * math.sqrt(sum2))

def search_past_incidents(query_text: str, limit: int = 2) -> List[Dict[str, Any]]:
    """
    Queries past incident memory and returns semantically similar historical failures.
    Uses local cosine similarity calculation for cross-db compatibility (Postgres/SQLite).
    """
    db = database.SessionLocal()
    try:
        query_embedding = get_embedding(query_text)
        records = db.query(PastIncidentRecord).all()
        
        matches = []
        for r in records:
            r_embedding = r.symptoms_embedding
            if not r_embedding:
                r_embedding = get_embedding(r.symptoms_text)
                
            sim = cosine_similarity(query_embedding, r_embedding)
            matches.append((sim, r))
            
        # Sort by similarity descending
        matches.sort(key=lambda x: x[0], reverse=True)
        
        results = []
        for sim, r in matches[:limit]:
            if sim > 0.1:  # Relevance threshold
                results.append({
                    "id": r.id,
                    "symptoms_text": r.symptoms_text,
                    "root_cause": r.root_cause,
                    "evidence_chain": r.evidence_chain,
                    "fix_diff": r.fix_diff,
                    "verification_metrics": r.verification_metrics,
                    "similarity": round(sim, 4)
                })
        return results
    except Exception as e:
        logger.error(f"Failed to query long-term memory: {e}")
        return []
    finally:
        db.close()

def save_to_incident_memory(symptoms_text: str, root_cause: str, evidence_chain: Dict[str, Any], fix_diff: str, verification_metrics: Dict[str, Any]):
    """
    Saves a resolved incident into long-term memory.
    """
    db = database.SessionLocal()
    try:
        embedding = get_embedding(symptoms_text)
        new_record = PastIncidentRecord(
            id=f"PAST-INC-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            symptoms_text=symptoms_text,
            root_cause=root_cause,
            evidence_chain=evidence_chain,
            fix_diff=fix_diff,
            verification_metrics=verification_metrics,
            symptoms_embedding=embedding
        )
        db.add(new_record)
        db.commit()
        logger.info(f"Successfully saved resolved incident to long-term memory: {new_record.id}")
    except Exception as e:
        logger.error(f"Failed to save incident to long-term memory: {e}")
    finally:
        db.close()
