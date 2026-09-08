from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime

class Evidence(BaseModel):
    id: str = Field(description="Unique identifier for this evidence")
    source: str = Field(description="Where the evidence came from (e.g., logs, git, metric_anomaly)")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    evidence_type: str = Field(description="Type of evidence: LOG, METRIC, TRACE, GIT, EXPERIMENT")
    content: Any = Field(description="Raw or structured content representing the evidence")
    relevance: str = Field(description="Explanation of why this is relevant")
    reliability: float = Field(default=1.0, description="Reliability score from 0.0 to 1.0")
    hypothesis_association: Optional[str] = Field(None, description="Hypothesis ID this evidence relates to")

class Hypothesis(BaseModel):
    id: str = Field(description="Unique identifier (e.g., H1, H2)")
    description: str = Field(description="Hypothesis description")
    supporting_evidence: List[str] = Field(default_factory=list, description="List of evidence IDs supporting this")
    contradicting_evidence: List[str] = Field(default_factory=list, description="List of evidence IDs contradicting this")
    probability: float = Field(default=0.0, description="Bayesian or heuristic confidence probability (0.0 to 1.0)")
    tests_to_validate: List[str] = Field(default_factory=list, description="List of test descriptions to validate this")
    tests_to_falsify: List[str] = Field(default_factory=list, description="List of test descriptions to falsify this")
    status: str = Field(default="ACTIVE", description="ACTIVE, FALSIFIED, VERIFIED")

class Experiment(BaseModel):
    id: str = Field(description="Unique experiment ID")
    hypothesis_id: str = Field(description="Hypothesis ID this experiment targets")
    name: str = Field(description="Name of the experiment")
    description: str = Field(description="Description of what this experiment tests")
    script: str = Field(description="Python code or shell command to execute in sandbox")
    status: str = Field(default="PENDING", description="PENDING, RUNNING, COMPLETED, FAILED")
    result: Optional[Dict[str, Any]] = None

class TimelineEvent(BaseModel):
    timestamp: str
    event_type: str  # DEPLOYMENT, ALERT, DB_MIGRATION, CONFIG_CHANGE
    description: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
