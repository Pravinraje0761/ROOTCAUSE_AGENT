import os
import sys
import time
import uuid
import asyncio
from typing import Dict, Any, List

# Configure relative imports for CLI execution
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.simulator import sim_state
from backend.app.tools import run_sandbox_script
from backend.app.agent import verify_fix_node, RootCauseState, DIAGNOSTIC_SCRIPTS, REPRODUCTION_SCRIPT

async def run_react_baseline(scenario: Dict[str, Any]) -> Dict[str, Any]:
    """
    ReAct baseline:
    Uses a standard Thought -> Action -> Observation loop. It chooses experiments
    sequentially based on the observation outputs, rather than tracking an explicit
    probability vector or calculating information gain.
    """
    print(f"\n[BASELINE REACT] Running Scenario #{scenario['id']}: {scenario['name']}...")
    
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
    
    t0 = time.time()
    steps = 0
    llm_calls = 0
    experiments = []
    
    # Pre-defined preference order representing standard heuristic/LLM search order for symptoms
    # Latency -> H5 first
    # Accuracy drop -> H3, then H1, H2, H4
    if fault == "resource_limit":
        search_order = ["H5", "H1", "H2", "H3", "H4"]
    else:
        search_order = ["H3", "H1", "H2", "H4", "H5"]
        
    confirmed_root_cause = None
    
    for h_id in search_order:
        steps += 1
        llm_calls += 1 # Thought/Action step
        
        # Execute diagnostic in sandbox
        script = DIAGNOSTIC_SCRIPTS.get(h_id, "")
        sandbox_res = run_sandbox_script(script)
        
        experiments.append(h_id)
        
        stdout = sandbox_res["stdout"]
        
        # Check if symptom matched (Observation)
        found = False
        if h_id == "H3" and "PREPROCESSING_MISMATCH: TRUE" in stdout:
            found = True
        elif h_id == "H1" and "DRIFT_DETECTED: TRUE" in stdout:
            found = True
        elif h_id == "H2" and "MODEL_MISMATCH: TRUE" in stdout:
            found = True
        elif h_id == "H4" and "DEPENDENCY_ERROR: TRUE" in stdout:
            found = True
        elif h_id == "H5" and "QUEUE_LATENCY: TRUE" in stdout:
            found = True
            
        if found:
            confirmed_root_cause = h_id
            break
            
    # Fallback if none matched
    if not confirmed_root_cause:
        confirmed_root_cause = search_order[0]
        
    # Reconstruct final state to apply patch
    state = {
        "incident_id": scenario["id"],
        "incident_type": scenario["type"],
        "severity": "HIGH",
        "symptoms": symptoms,
        "timeline": [],
        "observations": [],
        "evidence": [],
        "hypotheses": [],
        "experiments": [{"hypothesis_id": exp} for exp in experiments],
        "experiment_results": [],
        "belief_scores": {},
        "candidate_root_causes": [],
        "confirmed_root_cause": confirmed_root_cause,
        "confidence": 1.0 if confirmed_root_cause in experiments else 0.20,
        "actions_taken": [],
        "failed_actions": [],
        "next_action": "PROPOSE_FIX",
        "human_approval_required": False,
        "investigation_status": "VERIFYING",
        "logs": [f"ReAct agent identified root cause: {confirmed_root_cause}"]
    }
    
    # Apply patch and verify
    res_state = verify_fix_node(state)
    state = {**state, **res_state}
    llm_calls += 1 # Fix generation call
    
    duration = time.time() - t0
    
    success = state["investigation_status"] == "RESOLVED"
    matched_cause = state["confirmed_root_cause"] == scenario["expected_cause"]
    tool_calls = len(experiments)
    
    return {
        "scenario_id": scenario["id"],
        "name": scenario["name"],
        "success": success,
        "matched_cause": matched_cause,
        "steps": steps + 2, # Triage + Search steps + Verification
        "tool_calls": tool_calls,
        "llm_calls": llm_calls,
        "cost": round(llm_calls * 0.04, 3), # cost per decision
        "duration_s": round(duration, 3),
        "confidence": round(state.get("confidence", 0.0) * 100, 1),
        "status": state["investigation_status"]
    }
