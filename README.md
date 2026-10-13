# RootCause AI

[![CI](https://github.com/Pravinraje0761/ROOTCAUSE_AGENT/actions/workflows/ci.yml/badge.svg)](https://github.com/Pravinraje0761/ROOTCAUSE_AGENT/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

An agent that investigates production failures the way an engineer would: gather evidence,
propose competing hypotheses, run the experiment that is expected to be most informative,
update its beliefs, reproduce the failure in a sandbox, then propose a patch and verify it.
It is built as a LangGraph state machine behind a FastAPI service, with a React dashboard.

> **Scope.** Telemetry, git history and the five failure scenarios are **simulated**
> (`backend/app/simulator.py`). The agent investigates a real application in its sandbox
> (the [NeoGuard](https://github.com/Pravinraje0761/neogaurd) service), but the faults are
> injected by the simulator. Hypothesis generation and belief updates are rule-based and
> Bayesian; the agent does not call an LLM.

---

## How it works

- **Investigation loop:** triage → evidence → hypotheses → experiment → belief update →
  reproduction → fix → verification (`backend/app/agent.py`).
- **Experiment selection:** each candidate experiment is scored by expected information gain
  (Shannon entropy reduction under a 95%-sensitive, 95%-specific diagnostic).
- **Sandbox:** diagnostic scripts run in a Docker container when Docker is available, and in a
  local subprocess otherwise (`backend/app/sandbox.py`).
- **Approval gate:** read-only actions run automatically, sandbox actions are logged, and
  production patches stop for human approval.
- **Incident memory:** past incidents are stored in PostgreSQL (SQLite fallback) and
  retrieved by cosine similarity over keyword-feature vectors (`backend/app/memory.py`).

## 📐 System Architecture

```mermaid
graph TD
    User([User / Operator]) -->|Trigger Incident Investigation| Ingestion[Incident Ingestion API]
    Ingestion -->|Trigger Run| Controller[Controller Agent / LangGraph Orchestrator]
    
    subgraph Agent Loop [Core Agentic State Machine]
        Controller -->|Triage Incident| Triage[Triage Engine]
        Controller -->|Analyze State & Update Plan| Planner[Planning Engine]
        Controller -->|Query System Info| Evidence[Evidence Analyzer]
        Controller -->|Generate Competing Ideas| HypoEngine[Hypothesis Engine]
        Controller -->|Propose Experiments| ExpPlanner[Experiment Planner]
        Controller -->|Verify Fixes & Root Cause| Verifier[Verification Agent]
        Controller -->|Generate Patch| FixAgent[Fix Generator]
    end
    
    Controller <-->|Read/Write State| StateStore[(PostgreSQL state_store)]
    Controller <-->|Semantic Past Cases| MemStore[(PostgreSQL + pgvector)]
    
    subgraph Tool Layer [External Integrations]
        Planner -->|Execute Tool| ToolRouter{Tool Router}
        ToolRouter -->|Metrics/Logs/Traces| MockTelemetry[Simulated OTEL/Prometheus/Loki API]
        ToolRouter -->|Git Log/Diff| MockGit[Simulated Git Client]
        ToolRouter -->|Run Code/Tests| Sandbox[Docker Sandbox Execution Manager]
    end
    
    Sandbox -->|Create Isolation| Docker[Isolated Docker Container]
    Docker -->|Execute Diagnostic Scripts| CodeRunner[Python Runtime]
    
    Controller -->|Request Approval| Approval[Human-in-the-Loop Gateway]
    Approval -->|Approve/Deny Action| User
```

---

## Evaluation

`evaluation/run_sweep.py` runs the agent and four baselines on the five simulated scenarios:

| Method | Root cause found | Experiments run | Brier score (lower is better) |
|---|--:|--:|--:|
| Random experiment order | 100% | 3.2 | 0.044 |
| Prior-only (single guess, no experiments) | 40% | 0.0 | 0.778 |
| ReAct-style | 100% | 2.2 | 0.253 |
| Bayesian, fixed experiment order | 100% | 2.0 | 0.039 |
| **RootCause (Bayesian + information gain)** | **100%** | 3.0 | **0.022** |

What this does and does not show:

- Any method that runs experiments finds the cause in all five scenarios, so **accuracy does not
  separate them here**; the scenarios are too easy to do that.
- RootCause ends with the best-calibrated beliefs (lowest Brier score), but its margin over the
  plain Bayesian baseline is small, and that baseline needs fewer experiments.
- Five scenarios are too few for any difference to be statistically meaningful. A larger, harder
  scenario set is the main next step.
- The sweep also prints "LLM calls" and "cost" columns; these are modelled from the number of
  tool calls, not measured from real API usage.

`python benchmark.py` runs the agent alone on each scenario and prints its trace.

## Setup

```bash
git clone https://github.com/Pravinraje0761/ROOTCAUSE_AGENT.git
cd ROOTCAUSE_AGENT
python -m venv venv && source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt

# The application the agent investigates:
git clone https://github.com/Pravinraje0761/neogaurd.git WE_WILL_WIN/neoguard_app
#   (or point TARGET_APP_DIR at another copy)

pytest                                   # 26 tests
python evaluation/run_sweep.py           # baseline comparison
uvicorn backend.app.main:app --port 8000 # API
cd frontend && npm install && npm run dev  # dashboard on http://localhost:3000
```

With Docker: `docker-compose up --build` starts PostgreSQL, the API and the dashboard.

## 🖥️ Demo Scenarios

The dashboard exposes five simulated fault scenarios:
1.  **#104 Preprocessing**: Replaces MinMax features scaling with Standard normalizer, with an illustrative scripted accuracy drop from 94.2% to 71.3%.
2.  **#105 Version Mismatch**: Deploys an uncalibrated version of the classifier.
3.  **#106 Data Drift**: Shifts production input data features, simulating client-side covariate changes.
4.  **#107 Dependency Upgrade**: Introduces library upgrade truncating floats and reducing precision.
5.  **#108 Latency Lock**: Artificially limits worker thread pool concurrency to 1, causing a simulated latency spike to 2.4 s.

## License

[MIT](LICENSE)
