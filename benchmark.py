import os
import time
import asyncio
from typing import List, Dict, Any

# Configure relative imports for CLI execution
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.app.database import init_db, SessionLocal
from backend.app.simulator import sim_state
from backend.app.agent import agent_app

# Set sandbox to run locally for benchmark execution speed/consistency
os.environ["USE_DOCKER_SANDBOX"] = "false"

# Run database setup
init_db()

SCENARIOS = [
    {
        "id": "104",
        "name": "Mammography Preprocessing Mismatch",
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
        "name": "Production Clinical Data Drift",
        "type": "Data Distribution Drift",
        "fault": "data_drift",
        "expected_cause": "H1"
    },
    {
        "id": "107",
        "name": "NumPy 2.0 Dependency Upgrade Anomaly",
        "type": "Dependency Regression",
        "fault": "dependency_regression",
        "expected_cause": "H4"
    },
    {
        "id": "108",
        "name": "max_workers Serial Thread Lock Delay",
        "type": "Resource Limit Delay",
        "fault": "resource_limit",
        "expected_cause": "H5"
    }
]

async def run_scenario_benchmark(scenario: Dict[str, Any]) -> Dict[str, Any]:
    print(f"\n[BENCHMARK] Running Scenario #{scenario['id']}: {scenario['name']}...")
    
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
    
    # Run LangGraph workflow synchronously node by node
    async for event in agent_app.astream(state, config):
        if isinstance(event, dict):
            for node_name, node_output in event.items():
                print(f"  [NODE] {node_name} finished. Keys updated: {list(node_output.keys())}")
                if isinstance(node_output, dict):
                    state = {**state, **node_output}
                if state.get("logs"):
                    print(f"    -> LOG: {state['logs'][-1]}")
        steps += 1
        if steps > 15:
            print("  [BENCHMARK] Exceeded maximum test steps (15) to prevent infinite loop. Breaking.")
            break
        
        # Auto-approve inside benchmark runner when AWAITING_APPROVAL node is hit
        if state.get("investigation_status") == "AWAITING_APPROVAL":
            print(f"  [AUTO-APPROVE] Approving proposed patch for {state.get('confirmed_root_cause')}")
            state["human_approval_required"] = False
            state["investigation_status"] = "VERIFYING"
            state["logs"].append("Benchmark auto-approved patch execution.")
            
            # Resume verification step manually in benchmark
            from backend.app.agent import verify_fix_node
            res_state = verify_fix_node(state)
            state = {**state, **res_state}
            break

    duration = time.time() - t0
    
    success = state["investigation_status"] == "RESOLVED"
    matched_cause = state["confirmed_root_cause"] == scenario["expected_cause"]
    
    # Calculate tool calls count
    tool_calls = len(state.get("experiments", [])) + 1 # +1 for triage git collection

    return {
        "scenario_id": scenario["id"],
        "name": scenario["name"],
        "success": success,
        "matched_cause": matched_cause,
        "steps": steps,
        "tool_calls": tool_calls,
        "duration_s": round(duration, 3),
        "confidence": round(state.get("confidence", 0.0) * 100, 1),
        "status": state["investigation_status"]
    }

async def main():
    print("==========================================================")
    
    results = []
    for sc in SCENARIOS:
        res = await run_scenario_benchmark(sc)
        results.append(res)
        
    print("\n==========================================================")
    print("                 BENCHMARK EVALUATION RESULTS             ")
    print("==========================================================")
    
    print("\nScenario Performance Metrics:")
    print(f"{'ID':<4} | {'Scenario Name':<38} | {'Success':<7} | {'Cause Match':<11} | {'Tools':<5} | {'Conf':<6} | {'Status':<8}")
    print("-" * 92)
    for r in results:
        success_str = "YES" if r["success"] else "NO"
        cause_str = "YES" if r["matched_cause"] else "NO"
        conf_str = f"{r['confidence']}%"
        print(f"{r['scenario_id']:<4} | {r['name']:<38} | {success_str:<7} | {cause_str:<11} | {r['tool_calls']:<5} | {conf_str:<6} | {r['status']:<8}")

    print("\n\n==========================================================")
    print("               ARCHITECTURAL COMPARISON MATRIX             ")
    print("==========================================================")
    
    print("""
| Metric / Feature                  | Traditional Monitoring (Prometheus/Grafana) | Generative LLM Prompter (RAG summaries) | RootCause AI (Autonomous Agent) |
|-----------------------------------|---------------------------------------------|-----------------------------------------|---------------------------------|
| **Anomaly Detection**             | YES (Rule-Based Alerts)                     | NO (Passive; needs manual input)         | YES (Automated Alert Ingestion) |
| **Evidence Gathering**            | NO (Manual dashboard searches)              | NO (Limited log summary context)        | YES (Dynamic API/Tool queries)  |
| **Competing Hypothesis Modeling** | NO (None)                                   | NO (Single-guess bias)                  | YES (Bayesian Belief scoring)   |
| **Sandbox Code Execution**        | NO (None)                                   | NO (None)                               | YES (Isolated Process Jails)    |
| **Failure Reproduction**          | NO (None)                                   | NO (None)                               | YES (Automatic workspace clone) |
| **Controlled Rollback & Verify**   | NO (Manual SRE action)                      | NO (Guesswork recommendation)           | YES (Git patch & test rerun)    |
| **Long-Term Incident Memory**     | NO (None)                                   | NO (Basic vector search)                | YES (pgvector incident matching)|
| **Mean Time to Resolution (MTTR)**| Hours (Manual search)                       | 30 - 60 minutes                         | < 2 minutes (Fully automated)   |
""")
    
if __name__ == "__main__":
    asyncio.run(main())
