"""Smoke tests — verify all modules import without error."""

import os
os.environ["USE_DOCKER_SANDBOX"] = "false"

def test_import_simulator():
    from backend.app.simulator import sim_state, EVAL_DATASET, GIT_HISTORY, DEPLOYMENT_HISTORY
    assert len(EVAL_DATASET) == 100
    assert len(GIT_HISTORY) == 3
    assert len(DEPLOYMENT_HISTORY) == 2

def test_import_tools():
    from backend.app.tools import (
        get_metrics, get_logs, get_git_commits, get_git_diff,
        get_deployment_history, run_sandbox_script,
        get_traces, inspect_dataset, inspect_model
    )
    assert callable(get_metrics)
    assert callable(inspect_model)

def test_import_hypothesis():
    from backend.app.hypothesis import HypothesisEngine, INITIAL_HYPOTHESES
    assert len(INITIAL_HYPOTHESES) == 5

def test_import_state():
    from backend.app.state import RootCauseState, VerificationScore, FinalReport
    assert "hypotheses" in RootCauseState.__annotations__

def test_import_agent():
    from backend.app.agent import agent_app, triage_node, planning_node
    assert agent_app is not None

def test_import_database():
    from backend.app.database import init_db, SessionLocal, IncidentRecord
    assert callable(init_db)

def test_import_memory():
    from backend.app.memory import search_past_incidents, save_to_incident_memory
    assert callable(search_past_incidents)

def test_import_main():
    from backend.app.main import app
    assert app.title == "RootCause AI API"

def test_import_sandbox():
    from backend.app.sandbox import sandbox_manager
    assert sandbox_manager is not None
