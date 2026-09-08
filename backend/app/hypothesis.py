import logging
from typing import List, Dict, Any, Tuple
from backend.app.models import Hypothesis, Evidence

logger = logging.getLogger(__name__)

# Core Hypotheses Definitions
INITIAL_HYPOTHESES = [
    {
        "id": "H1",
        "description": "Production Data Drift: Input distribution shifted relative to training baseline.",
        "supporting_evidence": [],
        "contradicting_evidence": [],
        "probability": 0.20,
        "tests_to_validate": ["Compare production feature distributions with historical training baselines."],
        "tests_to_falsify": ["Prove production features align with historical training parameters."],
        "status": "ACTIVE"
    },
    {
        "id": "H2",
        "description": "Wrong Model Version: Uncalibrated or outdated model binary loaded in inference pipeline.",
        "supporting_evidence": [],
        "contradicting_evidence": [],
        "probability": 0.20,
        "tests_to_validate": ["Verify active model metadata, checkpoint hash, and registry configuration."],
        "tests_to_falsify": ["Verify active model metadata matches production release specification."],
        "status": "ACTIVE"
    },
    {
        "id": "H3",
        "description": "Preprocessing Mismatch: Changes in feature normalization scaling (e.g. MinMax vs Standard scaling).",
        "supporting_evidence": [],
        "contradicting_evidence": [],
        "probability": 0.40,
        "tests_to_validate": ["Compare pre-deployment and post-deployment preprocessing scaling outputs on validation set."],
        "tests_to_falsify": ["Verify preprocessing scaling outputs are mathematically identical to baseline."],
        "status": "ACTIVE"
    },
    {
        "id": "H4",
        "description": "Dependency Regression: Package upgrade (e.g. NumPy 2.0) causing calculation rounding variance.",
        "supporting_evidence": [],
        "contradicting_evidence": [],
        "probability": 0.10,
        "tests_to_validate": ["Run parity tests between runtime dependency environment and baseline environment."],
        "tests_to_falsify": ["Verify library computations match baseline outcomes across sample set."],
        "status": "ACTIVE"
    },
    {
        "id": "H5",
        "description": "Resource / Threading Configuration: Low max_workers setting or memory leak causing queueing latency.",
        "supporting_evidence": [],
        "contradicting_evidence": [],
        "probability": 0.10,
        "tests_to_validate": ["Inspect system latency profile under varying request concurrency levels."],
        "tests_to_falsify": ["Show latency remains constant under concurrent load tests."],
        "status": "ACTIVE"
    }
]

class HypothesisEngine:
    @staticmethod
    def get_initial_hypotheses(incident_type: str, symptoms: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generates initial hypothesis list based on triaged incident type.
        """
        hypos = [h.copy() for h in INITIAL_HYPOTHESES]
        
        # Adjust probabilities based on symptoms
        latency = symptoms.get("latency", 0.18)
        accuracy = symptoms.get("accuracy", 0.94)
        error_rate = symptoms.get("error_rate", 0.0)
        
        if latency > 1.0:
            # Latency incident
            for h in hypos:
                if h["id"] == "H5":
                    h["probability"] = 0.70
                else:
                    h["probability"] = 0.075
        elif accuracy < 0.85:
            # Accuracy drop incident
            for h in hypos:
                if h["id"] == "H3":
                    h["probability"] = 0.45
                elif h["id"] == "H1":
                    h["probability"] = 0.25
                elif h["id"] == "H2":
                    h["probability"] = 0.20
                elif h["id"] == "H4":
                    h["probability"] = 0.10
                else:
                    h["probability"] = 0.0
        return hypos

    @staticmethod
    def update_beliefs(hypotheses: List[Dict[str, Any]], evidence_list: List[Dict[str, Any]], experiment_results: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, float]]:
        """
        Performs transparent Bayesian-like belief updating using evidence and experiment results.
        Returns: Tuple of updated hypotheses list and dictionary of final belief scores.
        """
        # Start with base scores from current hypotheses
        scores = {h["id"]: h["probability"] for h in hypotheses}
        
        # Track associated evidence
        evidence_ids = {e["id"]: e for e in evidence_list}
        
        # 1. Evaluate Timeline Evidence
        # If there is a git commit affecting preprocessing -> boost H3
        # If there is a git commit affecting config/workers -> boost H5
        # If there is a git commit affecting models -> boost H2
        git_commits = [e for e in evidence_list if e["evidence_type"] == "GIT"]
        has_preprocessing_diff = False
        has_config_diff = False
        
        for e in git_commits:
            content = str(e["content"])
            if "preprocessing" in content or "scale" in content:
                has_preprocessing_diff = True
            if "max_workers" in content or "workers" in content or "config" in content:
                has_config_diff = True
                
        # 2. Process Experiment Results
        for result in experiment_results:
            script_out = result.get("result", {}).get("stdout", "")
            script_err = result.get("result", {}).get("stderr", "")
            target_hypo = result.get("hypothesis_id")
            
            if not target_hypo:
                continue

            # Target H3: Preprocessing
            if target_hypo == "H3":
                if "PREPROCESSING_MISMATCH: TRUE" in script_out or "normalization mismatch detected" in script_out.lower():
                    # High positive evidence
                    scores["H3"] *= 4.0
                    scores["H1"] *= 0.1
                    scores["H2"] *= 0.2
                    scores["H4"] *= 0.3
                    scores["H5"] *= 0.1
                elif "PREPROCESSING_MISMATCH: FALSE" in script_out:
                    # Falsified
                    scores["H3"] = 0.01

            # Target H1: Data Drift
            if target_hypo == "H1":
                if "DRIFT_DETECTED: TRUE" in script_out:
                    scores["H1"] *= 3.0
                    scores["H3"] *= 0.4
                    scores["H2"] *= 0.4
                elif "DRIFT_DETECTED: FALSE" in script_out:
                    scores["H1"] = 0.02

            # Target H2: Model Mismatch
            if target_hypo == "H2":
                if "MODEL_MISMATCH: TRUE" in script_out or "loaded wrong model version" in script_out.lower():
                    scores["H2"] *= 4.0
                    scores["H3"] *= 0.2
                    scores["H1"] *= 0.2
                elif "MODEL_MISMATCH: FALSE" in script_out:
                    scores["H2"] = 0.01

            # Target H4: Dependency Version Mismatch
            if target_hypo == "H4":
                if "DEPENDENCY_ERROR: TRUE" in script_out:
                    scores["H4"] *= 3.5
                    scores["H3"] *= 0.3
                    scores["H1"] *= 0.3
                elif "DEPENDENCY_ERROR: FALSE" in script_out:
                    scores["H4"] = 0.02

            # Target H5: Resource Limit
            if target_hypo == "H5":
                if "QUEUE_LATENCY: TRUE" in script_out or "latency spike verified" in script_out.lower():
                    scores["H5"] *= 5.0
                    scores["H3"] *= 0.1
                elif "QUEUE_LATENCY: FALSE" in script_out:
                    scores["H5"] = 0.01

        # Apply Git Timeline updates if no experiments have run yet to give starting updates
        if not experiment_results:
            if has_preprocessing_diff:
                scores["H3"] *= 2.0
                scores["H1"] *= 0.5
            if has_config_diff:
                scores["H5"] *= 2.5
                scores["H1"] *= 0.5

        # Normalize probabilities so they sum to 1.0
        total = sum(scores.values())
        if total > 0:
            scores = {k: round(v / total, 4) for k, v in scores.items()}
        else:
            # fallback
            scores = {h["id"]: 1.0 / len(hypotheses) for h in hypotheses}

        # Update status and scores on hypotheses objects
        for h in hypotheses:
            h_id = h["id"]
            h["probability"] = scores[h_id]

            # Falsification check
            if scores[h_id] < 0.05:
                h["status"] = "FALSIFIED"
            elif scores[h_id] > 0.80:
                h["status"] = "VERIFIED"
            else:
                h["status"] = "ACTIVE"

            # Associate evidence
            for e in evidence_list:
                assoc = e.get("hypothesis_association")
                if assoc == h_id:
                    if e["id"] not in h["supporting_evidence"]:
                        h["supporting_evidence"].append(e["id"])
                elif assoc is not None and assoc != h_id:
                    # Evidence associated with a different hypothesis contradicts this one
                    if e["id"] not in h["contradicting_evidence"]:
                        h["contradicting_evidence"].append(e["id"])

        return hypotheses, scores
