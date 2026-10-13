"""Agent node-level tests — verify each graph node produces correct output."""

import os
os.environ["USE_DOCKER_SANDBOX"] = "false"

from backend.app.simulator import sim_state
from backend.app.agent import (
    triage_node, planning_node, execution_node,
    belief_update_node, fix_generation_node, verify_fix_node,
    compute_information_gain, classify_risk
)


def _base_state(fault: str = "preprocessing_mismatch"):
    sim_state.reset()
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

    return {
        "incident_id": "test-001",
        "incident_type": "ML Performance Degradation",
        "severity": "HIGH",
        "symptoms": {"accuracy": 0.713, "latency": 0.18, "error_rate": 0.178},
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
        "logs": [],
        "risk_level": "GREEN",
        "final_report": None,
    }


def test_triage_node():
    state = _base_state()
    result = triage_node(state)

    assert len(result["evidence"]) >= 8, "Should collect metrics, logs, traces, git, dataset, model evidence"
    assert len(result["hypotheses"]) == 5
    assert result["investigation_status"] == "PLANNING"
    assert len(result["timeline"]) >= 2
    assert result["risk_level"] == "GREEN"

    evidence_types = {e["evidence_type"] for e in result["evidence"]}
    expected_types = {"GIT", "METRIC", "LOG", "TRACE", "DATASET", "MODEL"}
    assert expected_types.issubset(evidence_types), f"Missing evidence types: {expected_types - evidence_types}"


def test_planning_node_selects_highest_info_gain():
    state = _base_state()
    triage_result = triage_node(state)
    state.update(triage_result)

    result = planning_node(state)
    assert result["investigation_status"] in ("EXPERIMENTING", "REPRODUCING")
    assert result["next_action"] is not None


def test_execution_node_diagnostic():
    state = _base_state()
    triage_result = triage_node(state)
    state.update(triage_result)
    plan_result = planning_node(state)
    state.update(plan_result)

    result = execution_node(state)
    assert len(result["experiments"]) >= 1
    assert result["investigation_status"] in ("BELIEF_UPDATE", "REPRODUCING")


def test_belief_update_node():
    state = _base_state()
    triage_result = triage_node(state)
    state.update(triage_result)
    plan_result = planning_node(state)
    state.update(plan_result)
    exec_result = execution_node(state)
    state.update(exec_result)

    result = belief_update_node(state)
    assert "hypotheses" in result
    scores = result["belief_scores"]
    total = sum(scores.values())
    assert abs(total - 1.0) < 0.01, f"Belief scores should sum to ~1.0, got {total}"


def test_compute_information_gain():
    # Maximal uncertainty: gain = 1 - H(0.05) bits for a 95%-sensitive/specific test.
    ig = compute_information_gain("H3", 0.5, set())
    assert abs(ig - 0.7136) < 1e-3
    # Nothing to learn from a hypothesis already tested or already resolved.
    assert compute_information_gain("H3", 0.5, {"H3"}) == 0.0
    assert compute_information_gain("H3", 0.99, set()) == 0.0
    # Less uncertainty, less to gain.
    assert compute_information_gain("H3", 0.3, set()) < ig


def test_classify_risk():
    assert classify_risk("read_metrics") == "GREEN"
    assert classify_risk("sandbox_diagnostic") == "YELLOW"
    assert classify_risk("apply_patch_production") == "RED"
    assert classify_risk("unknown_action") == "YELLOW"


def test_full_agent_h3():
    """End-to-end test for preprocessing mismatch (H3)."""
    state = _base_state("preprocessing_mismatch")
    config = {"configurable": {"thread_id": "test-h3"}}

    from backend.app.agent import agent_app
    import asyncio

    async def run():
        final = None
        async for event in agent_app.astream(state, config):
            if isinstance(event, dict):
                for node_name, node_output in event.items():
                    if isinstance(node_output, dict):
                        state.update(node_output)
            # Auto-approve
            if state.get("investigation_status") == "AWAITING_APPROVAL":
                state["human_approval_required"] = False
                state["investigation_status"] = "VERIFYING"
                res = verify_fix_node(state)
                state.update(res)
                break
        return state

    final_state = asyncio.run(run())
    assert final_state["confirmed_root_cause"] == "H3"
    assert final_state["investigation_status"] == "RESOLVED"


def test_full_agent_h5():
    """End-to-end test for resource limit (H5)."""
    state = _base_state("resource_limit")
    state["symptoms"] = {"accuracy": 0.942, "latency": 2.41, "error_rate": 0.12}
    config = {"configurable": {"thread_id": "test-h5"}}

    from backend.app.agent import agent_app
    import asyncio

    async def run():
        async for event in agent_app.astream(state, config):
            if isinstance(event, dict):
                for node_name, node_output in event.items():
                    if isinstance(node_output, dict):
                        state.update(node_output)
            if state.get("investigation_status") == "AWAITING_APPROVAL":
                state["human_approval_required"] = False
                state["investigation_status"] = "VERIFYING"
                res = verify_fix_node(state)
                state.update(res)
                break
        return state

    final_state = asyncio.run(run())
    assert final_state["confirmed_root_cause"] == "H5"
    assert final_state["investigation_status"] == "RESOLVED"
