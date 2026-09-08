import os
import sys
import time
import math
import asyncio
from typing import List, Dict, Any

# Configure relative imports for CLI execution
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.simulator import sim_state
from backend.app.agent import agent_app, verify_fix_node
from backend.app.hypothesis import HypothesisEngine

# Import baselines
from baselines.llm_only import run_llm_only_baseline
from baselines.react_agent import run_react_baseline
from baselines.random_agent import run_random_baseline
from baselines.bayesian_agent import run_bayesian_baseline

SCENARIOS = [
    {
        "id": "104",
        "name": "Preprocessing Mismatch",
        "type": "ML Performance Degradation",
        "fault": "preprocessing_mismatch",
        "expected_cause": "H3"
    },
    {
        "id": "105",
        "name": "Outdated Model Skew",
        "type": "Deployment Version Skew",
        "fault": "wrong_model",
        "expected_cause": "H2"
    },
    {
        "id": "106",
        "name": "Clinical Data Drift",
        "type": "Data Distribution Drift",
        "fault": "data_drift",
        "expected_cause": "H1"
    },
    {
        "id": "107",
        "name": "Dependency Upgrade Anomaly",
        "type": "Dependency Regression",
        "fault": "dependency_regression",
        "expected_cause": "H4"
    },
    {
        "id": "108",
        "name": "Serial Thread Lock Delay",
        "type": "Resource Limit Delay",
        "fault": "resource_limit",
        "expected_cause": "H5"
    }
]

def calculate_entropy(probs: Dict[str, float]) -> float:
    entropy = 0.0
    for p in probs.values():
        if p > 1e-9:
            entropy -= p * math.log2(p)
    return entropy

async def run_rootcause_agent_scenario(scenario: Dict[str, Any]) -> Dict[str, Any]:
    """Runs the primary RootCause (EIG + Bayesian) agent on a scenario."""
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

    symptoms = {
        "accuracy": 0.713 if fault != "resource_limit" else 0.942,
        "latency": 0.18 if fault != "resource_limit" else 2.41,
        "error_rate": 0.178 if fault != "resource_limit" else 0.12
    }
    
    state = {
        "incident_id": scenario["id"],
        "incident_type": scenario["type"],
        "severity": "HIGH",
        "symptoms": symptoms,
        "timeline": [],
        "observations": [],
        "evidence": [],
        "hypotheses": [],
        "experiments": [],
        "experiment_results": [],
        "belief_scores": {},
        "candidate_root_causes": [],
        "confirmed_root_cause": None,
        "confidence": 0.0,
        "actions_taken": [],
        "failed_actions": [],
        "next_action": None,
        "human_approval_required": False,
        "investigation_status": "TRIAGING",
        "logs": []
    }
    
    t0 = time.time()
    steps = 0
    config = {"configurable": {"thread_id": scenario["id"]}}
    
    async for event in agent_app.astream(state, config):
        if isinstance(event, dict):
            for node_name, node_output in event.items():
                if isinstance(node_output, dict):
                    state = {**state, **node_output}
        steps += 1
        if steps > 15:
            break
        
        if state.get("investigation_status") == "AWAITING_APPROVAL":
            state["human_approval_required"] = False
            state["investigation_status"] = "VERIFYING"
            res_state = verify_fix_node(state)
            state = {**state, **res_state}
            break

    duration = time.time() - t0
    success = state["investigation_status"] == "RESOLVED"
    matched_cause = state["confirmed_root_cause"] == scenario["expected_cause"]
    tool_calls = len(state.get("experiments", []))
    
    # RootCause EIG planning uses ~1 LLM call per triage decision + 1 for fix patch
    llm_calls = tool_calls + 1 
    
    return {
        "scenario_id": scenario["id"],
        "name": scenario["name"],
        "success": success,
        "matched_cause": matched_cause,
        "steps": steps,
        "tool_calls": tool_calls,
        "llm_calls": llm_calls,
        "cost": round(llm_calls * 0.03, 3),
        "duration_s": round(duration, 3),
        "confidence": round(state.get("confidence", 0.0) * 100, 1),
        "status": state["investigation_status"],
        "final_beliefs": state.get("belief_scores", {})
    }

async def run_sweep():
    print("=========================================================================")
    print("                 ROOTCAUSE AI METRICS COMPARATIVE SWEEP                 ")
    print("=========================================================================")
    
    methods = {
        "Random": run_random_baseline,
        "LLM-Only": run_llm_only_baseline,
        "ReAct": run_react_baseline,
        "Bayesian (non-EIG)": run_bayesian_baseline,
        "RootCause (EIG)": run_rootcause_agent_scenario
    }
    
    # Initialize metric logs
    summary_data = {m: {"accuracy": 0.0, "experiments": 0.0, "llm_calls": 0.0, "cost": 0.0, "brier_score": 0.0, "ue": 0.0} for m in methods}
    
    # Base initial entropy for 5 hypotheses with priors (0.2, 0.2, 0.4, 0.1, 0.1)
    h_initial = -(2 * 0.2 * math.log2(0.2) + 0.4 * math.log2(0.4) + 2 * 0.1 * math.log2(0.1))
    
    for method_name, runner in methods.items():
        print(f"\nEvaluating method: {method_name}...")
        total_acc = 0
        total_exp = 0
        total_llm = 0
        total_cost = 0.0
        total_brier = 0.0
        total_ue = 0.0
        
        for sc in SCENARIOS:
            # Run
            if method_name == "RootCause (EIG)":
                res = await runner(sc)
            else:
                res = await runner(sc)
                
            # Accuracy
            acc = 1.0 if res["matched_cause"] and res["success"] else 0.0
            total_acc += acc
            total_exp += res["tool_calls"]
            total_llm += res["llm_calls"]
            total_cost += res["cost"]
            
            # Extract final belief vector or mock it for non-bayesian models
            final_beliefs = res.get("final_beliefs", {})
            if not final_beliefs:
                # Mock belief mapping for non-Bayesian baselines to calculate Brier score & entropy
                # LLM-only and ReAct assign 100% confidence to their selected cause
                final_beliefs = {h: 0.0 for h in ["H1", "H2", "H3", "H4", "H5"]}
                final_beliefs[res["scenario_id"]] = res["confidence"] / 100.0
                # Normalize others
                rem = 1.0 - (res["confidence"] / 100.0)
                other_count = len(final_beliefs) - 1
                for h in final_beliefs:
                    if h != res["scenario_id"]:
                        final_beliefs[h] = rem / other_count

            # Multi-class Brier Score calculation
            brier = 0.0
            for h_id, p in final_beliefs.items():
                y = 1.0 if h_id == sc["expected_cause"] else 0.0
                brier += (p - y) ** 2
            total_brier += brier
            
            # Uncertainty Efficiency (UE) calculation
            h_final = calculate_entropy(final_beliefs)
            diag_cost = max(0.01, 0.05 * res["tool_calls"] + res["cost"])
            ue = (h_initial - h_final) / diag_cost
            total_ue += max(0.0, ue)
            
        n = len(SCENARIOS)
        summary_data[method_name]["accuracy"] = (total_acc / n) * 100
        summary_data[method_name]["experiments"] = total_exp / n
        summary_data[method_name]["llm_calls"] = total_llm / n
        summary_data[method_name]["cost"] = total_cost / n
        summary_data[method_name]["brier_score"] = total_brier / n
        summary_data[method_name]["ue"] = total_ue / n

    # Print comparative results
    print("\n\n=========================================================================")
    print("                     COMPARATIVE RESEARCH MATRIX RESULT                  ")
    print("=========================================================================")
    print(f"{'Configuration':<20} | {'Accuracy':<8} | {'Experiments':<11} | {'LLM Calls':<9} | {'Avg Cost':<8} | {'Brier Score':<11} | {'Unc. Eff. (UE)':<14}")
    print("-" * 92)
    for m, metrics in summary_data.items():
        print(f"{m:<20} | {metrics['accuracy']:.1f}%   | {metrics['experiments']:<11.1f} | {metrics['llm_calls']:<9.1f} | ${metrics['cost']:.3f}  | {metrics['brier_score']:.3f}       | {metrics['ue']:.3f}")
    print("=========================================================================")
    
if __name__ == "__main__":
    asyncio.run(run_sweep())
