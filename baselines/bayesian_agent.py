import os
import sys
import time
import uuid
import asyncio
from typing import Dict, Any, List

# Configure relative imports for CLI execution
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.simulator import sim_state
from backend.app.hypothesis import HypothesisEngine
from backend.app.tools import run_sandbox_script
from backend.app.agent import verify_fix_node, RootCauseState, DIAGNOSTIC_SCRIPTS, REPRODUCTION_SCRIPT

async def run_bayesian_baseline(scenario: Dict[str, Any]) -> Dict[str, Any]:
    """
    Bayesian agent baseline (Non-EIG):
    Keeps the explicit Bayesian belief tracking state and runs active diagnostics.
    However, instead of using Shannon Information Gain, it selects the next hypothesis
    to test by picking the one with the highest prior probability from the remaining untested set.
    """
    print(f"\n[BASELINE BAYESIAN-NON-EIG] Running Scenario #{scenario['id']}: {scenario['name']}...")
    
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
        "confirmed_root_cause": None,
        "confidence": 0.0,
        "actions_taken": [],
        "failed_actions": [],
        "next_action": None,
        "human_approval_required": False,
        "investigation_status": "PLANNING",
        "logs": []
    }
    
    t0 = time.time()
    steps = 0
    llm_calls = 0
    tested_ids = set()
    
    # Loop representing planning -> execution -> belief update
    while state["investigation_status"] == "PLANNING" and steps < 10:
        steps += 1
        
        # Identify untested hypotheses
        untested = [h for h in state["hypotheses"] if h["id"] not in tested_ids]
        
        if not untested:
            # All tested, pick the highest confidence one
            highest_h = max(state["hypotheses"], key=lambda h: state["belief_scores"].get(h["id"], 0.0))
            state["confirmed_root_cause"] = highest_h["id"]
            state["confidence"] = state["belief_scores"][highest_h["id"]]
            state["investigation_status"] = "VERIFYING"
            break
            
        # Instead of EIG, pick the one with the highest current belief score (Baseline difference)
        selected_h = max(untested, key=lambda h: state["belief_scores"].get(h["id"], h["probability"]))
        h_id = selected_h["id"]
        tested_ids.add(h_id)
        
        # LLM call simulated for planning decision
        llm_calls += 1 
        
        # Execute diagnostic in sandbox
        script = DIAGNOSTIC_SCRIPTS.get(h_id, "")
        sandbox_res = run_sandbox_script(script)
        
        exp_event = {
            "id": f"EXP-{h_id}-{uuid.uuid4().hex[:4]}",
            "hypothesis_id": h_id,
            "name": f"Diagnostic experiment {h_id}",
            "description": f"Testing hypothesis {h_id}",
            "script": script,
            "status": "COMPLETED" if sandbox_res["exit_code"] == 0 else "FAILED",
            "result": sandbox_res
        }
        state["experiments"].append(exp_event)
        
        new_evidence = {
            "id": f"EVI-EXP-{h_id}",
            "source": f"sandbox:experiment_{h_id}",
            "timestamp": time.time(),
            "evidence_type": "EXPERIMENT",
            "content": sandbox_res["stdout"],
            "relevance": f"Execution result of diagnostic script for {h_id}.",
            "reliability": 1.0,
            "hypothesis_association": h_id
        }
        state["evidence"].append(new_evidence)
        
        # Bayesian update
        updated_hypos, new_scores = HypothesisEngine.update_beliefs(
            state["hypotheses"], state["evidence"], state["experiments"]
        )
        state["hypotheses"] = updated_hypos
        state["belief_scores"] = new_scores
        
        # Check if confidence threshold exceeded (80%)
        highest_score = max(new_scores.values())
        highest_id = max(new_scores, key=new_scores.get)
        
        if highest_score > 0.80:
            state["confirmed_root_cause"] = highest_id
            state["confidence"] = highest_score
            state["investigation_status"] = "VERIFYING"
            break
            
    # Apply patch and verify
    if state["investigation_status"] == "VERIFYING":
        res_state = verify_fix_node(state)
        state = {**state, **res_state}
        llm_calls += 1 # LLM call to generate fix
        
    duration = time.time() - t0
    
    success = state["investigation_status"] == "RESOLVED"
    matched_cause = state["confirmed_root_cause"] == scenario["expected_cause"]
    tool_calls = len(state["experiments"])
    
    return {
        "scenario_id": scenario["id"],
        "name": scenario["name"],
        "success": success,
        "matched_cause": matched_cause,
        "steps": steps + 2, # Loops + Triage + Verification
        "tool_calls": tool_calls,
        "llm_calls": llm_calls,
        "cost": round(llm_calls * 0.03, 3), 
        "duration_s": round(duration, 3),
        "confidence": round(state.get("confidence", 0.0) * 100, 1),
        "status": state["investigation_status"]
    }
