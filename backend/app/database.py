import logging
from sqlalchemy import create_engine, Column, String, Float, Text, JSON, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
from backend.app.config import settings

logger = logging.getLogger(__name__)

Base = declarative_base()

class IncidentRecord(Base):
    __tablename__ = "incidents"
    
    incident_id = Column(String, primary_key=True)
    incident_type = Column(String, nullable=False)
    status = Column(String, default="TRIAGED")
    state_json = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PastIncidentRecord(Base):
    __tablename__ = "past_incidents"
    
    id = Column(String, primary_key=True)
    symptoms_text = Column(Text, nullable=False)
    root_cause = Column(Text, nullable=False)
    evidence_chain = Column(JSON, nullable=False)
    fix_diff = Column(Text, nullable=False)
    verification_metrics = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # We will store embedding as JSON list of floats for SQLite/PostgreSQL fallback compatibility.
    # If pgvector extension is verified in PostgreSQL, we can use the Vector type from pgvector.sqlalchemy
    symptoms_embedding = Column(JSON, nullable=True)

class WorkspaceRecord(Base):
    """A connected source code workspace, available for real-codebase analysis."""
    __tablename__ = "workspaces"

    workspace_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    source = Column(String, nullable=False)  # 'github' | 'local'
    url = Column(Text, nullable=True)        # GitHub URL (github source)
    root = Column(Text, nullable=False)      # filesystem path to the repo
    branch = Column(String, nullable=True)
    metadata_json = Column(JSON, nullable=True)  # cached repo metadata snapshot
    connected_at = Column(DateTime, default=datetime.utcnow)
    last_analyzed_at = Column(DateTime, nullable=True)

class LiveIncidentRecord(Base):
    """A live investigation session on a connected workspace."""
    __tablename__ = "live_incidents"

    incident_id = Column(String, primary_key=True)
    workspace_id = Column(String, nullable=False)
    symptom = Column(Text, nullable=False)
    config_json = Column(JSON, nullable=True)
    status = Column(String, default="INVESTIGATING")  # INVESTIGATING | RESOLVED | UNRESOLVED
    understanding_json = Column(JSON, nullable=True)
    hypotheses_json = Column(JSON, nullable=True)
    iteration_results_json = Column(JSON, nullable=True)
    root_cause_json = Column(JSON, nullable=True)
    health_before_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Database Connection Initialization
engine = None
SessionLocal = None

def init_db():
    global engine, SessionLocal
    db_url = settings.database_url
    
    # Fallback to local SQLite if PostgreSQL connection fails
    try:
        if db_url.startswith("postgresql"):
            logger.info("Connecting to PostgreSQL database...")
            engine = create_engine(db_url, pool_pre_ping=True)
            # Test connection
            with engine.connect() as conn:
                pass
        else:
            raise ValueError("Non-postgres URL")
    except Exception as e:
        logger.warning(f"PostgreSQL connection failed ({e}). Falling back to Local SQLite database: sqlite:///rootcause.db")
        sqlite_url = "sqlite:///rootcause.db"
        engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})
        
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    # Pre-populate Past Incident Memory with some sample historical cases for retrieval demo
    db = SessionLocal()
    try:
        count = db.query(PastIncidentRecord).count()
        if count == 0:
            logger.info("Pre-populating historical incident memory database...")
            prepopulate_past_incidents(db)
    finally:
        db.close()

def prepopulate_past_incidents(db):
    # Incident 1: Normalization mismatch
    inc1 = PastIncidentRecord(
        id="PAST-INC-001",
        symptoms_text="Model accuracy dropped from 94% to 71% after deployment. Features output range out of bounds.",
        root_cause="Preprocessing scale mismatch. Commit updated MinMax to Standard scale without updating weights.",
        evidence_chain={
            "git_commit": "8f31a2c",
            "metric_drop": "Accuracy 71.3%",
            "sandbox_test": "PREPROCESSING_MISMATCH: TRUE"
        },
        fix_diff="Revert standard scaling features back to minmax scaling in preprocessing.py",
        verification_metrics={"before_accuracy": 0.713, "after_accuracy": 0.939},
        symptoms_embedding=[0.05] * 1536  # Simulated mock embedding
    )
    
    # Incident 2: Latency spike due to max_workers
    inc2 = PastIncidentRecord(
        id="PAST-INC-002",
        symptoms_text="API Latency spike to 2.4s. Thread queueing locks. No accuracy drop.",
        root_cause="max_workers configured to 1 in config.yaml causing serial queueing under concurrent load.",
        evidence_chain={
            "git_commit": "3b77e11",
            "metric_drop": "Latency 2.4s",
            "sandbox_test": "QUEUE_LATENCY: TRUE"
        },
        fix_diff="Change max_workers to 8 in config.yaml",
        verification_metrics={"before_latency": 2.4, "after_latency": 0.18},
        symptoms_embedding=[0.01] * 1536
    )
    
    db.add(inc1)
    db.add(inc2)
    db.commit()
