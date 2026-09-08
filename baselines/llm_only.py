import os
import sys
import time
import asyncio
from typing import Dict, Any

# Configure relative imports for CLI execution
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.simulator import sim_state
from backend.app.hypothesis import HypothesisEngine
from backend.app.agent import verify_fix_node, RootCauseState

async def run_llm_only_baseline(scenario: Dict[str, Any]) -> Dict[str, Any]:
    """
    LLM-Only baseline:
    Ingests symptoms, instantly selects the hypothesis with the highest prior probability,
    and directly generates/applies the patch without running any diagnostic experiments.
    """
    print(f"\n[BASELINE LLM-ONLY] Running Scenario #{scenario['id']}: {scenario['name']}...")
    
    # 1. Reset and inject fault
    sim_state.reset()
    fault = scenario["fault"]
    if fault == "preprocessing_mismatch":
        sim_state.preprocessing_mode = "standard_scaler"
        sim_state.latency_injection = 2.2
        sim_state.active_faults = ["preprocessing_mismatch"]
    elif fault == "wrong_model":
        sim_state.model_version = "v2.0.0-uncalibrated"
        sim_state.active_faults = ["wrong_model"]
    elif fault == "data_drift":
        sim_state.drift_multiplier = 1.8
        sim_state.active_faults = ["data_drift"]
    elif fault == "dependency_regression":
        sim_state.dependency_version = "2.0.0"
        sim_state.active_faults = ["dependency_regression"]
    elif fault == "resource_limit":
        sim_state.latency_injection = 2.4
        sim_state.active_faults = ["resource_limit"]

    # 2. Setup initial state
    symptoms = {
        "accuracy": 0.713 if fault != "resource_limit" else 0.942,
        "latency": 0.18 if fault != "resource_limit" else 2.41,
        "error_rate": 0.178 if fault != "resource_limit" else 0.12
    }
    
    # 3. Triage
    initial_hypos = HypothesisEngine.get_initial_hypotheses(scenario["type"], symptoms)
    
    # Select highest prior hypothesis (mocking LLM direct zero-shot guess)
    highest_h = max(initial_hypos, key=lambda h: h["probability"])
    confirmed_root_cause = highest_h["id"]
    
    # Construct final state to apply patch
    state = {
        "incident_id": scenario["id"],
        "incident_type": scenario["type"],
        "severity": "HIGH",
        "symptoms": symptoms,
        "timeline": [],
        "observations": [],
        "evidence": [],
        "hypotheses": initial_hypos,
        "experiments": [],
        "experiment_results": [],
        "belief_scores": {h["id"]: h["probability"] for h in initial_hypos},
        "candidate_root_causes": [],
        "confirmed_root_cause": confirmed_root_cause,
        "confidence": highest_h["probability"],
        "actions_taken": [],
        "failed_actions": [],
        "next_action": "PROPOSE_FIX",
        "human_approval_required": False,
        "investigation_status": "VERIFYING",
        "logs": [f"LLM-Only instantly guessed hypothesis: {confirmed_root_cause}"]
    }
    
    t0 = time.time()
    
    # Direct patch verification
    res_state = verify_fix_node(state)
    state = {**state, **res_state}
    
    duration = time.time() - t0
    
    success = state["investigation_status"] == "RESOLVED"
    matched_cause = state["confirmed_root_cause"] == scenario["expected_cause"]
    
    # Metrics
    # 1 LLM call to guess the cause, 0 diagnostic tests run.
    return {
        "scenario_id": scenario["id"],
        "name": scenario["name"],
        "success": success,
        "matched_cause": matched_cause,
        "steps": 2, # Triage + Patch
        "tool_calls": 0, # No diagnostic tools executed
        "llm_calls": 1, 
        "cost": 0.05, # Fixed hypothetical cost ($)
        "duration_s": round(duration, 3),
        "confidence": round(state.get("confidence", 0.0) * 100, 1),
        "status": state["investigation_status"]
    }
