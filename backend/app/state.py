from typing import TypedDict, List, Dict, Any, Optional

class VerificationScore(TypedDict):
    temporal_correlation: float
    code_correlation: float
    reproduction: float
    controlled_experiment: float
    rollback_recovery: float
    evidence_strength: float
    total: float
    breakdown: Dict[str, str]

class FinalReport(TypedDict):
    root_cause_id: str
    root_cause_description: str
    confidence: float
    verification_score: VerificationScore
    evidence_chain: List[Dict[str, Any]]
    experiments_run: int
    hypotheses_falsified: int
    timeline_summary: List[str]
    fix_description: str

class RootCauseState(TypedDict):
    incident_id: str
    incident_type: str
    severity: str
    symptoms: Dict[str, Any]
    timeline: List[Dict[str, Any]]
    observations: List[str]
    evidence: List[Dict[str, Any]]
    hypotheses: List[Dict[str, Any]]
    experiments: List[Dict[str, Any]]
    experiment_results: List[Dict[str, Any]]
    belief_scores: Dict[str, float]
    candidate_root_causes: List[str]
    confirmed_root_cause: Optional[str]
    confidence: float
    actions_taken: List[str]
    failed_actions: List[str]
    next_action: Optional[str]
    human_approval_required: bool
    investigation_status: str
    logs: List[str]
    risk_level: str
    final_report: Optional[FinalReport]
    causal_graph: Optional[Dict[str, Any]]
    counterfactual_verification: Optional[Dict[str, Any]]
