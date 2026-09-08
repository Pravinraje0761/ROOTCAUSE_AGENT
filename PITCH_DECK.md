# RootCause AI: Hackathon Presentation & Pitch Deck

This document serves as the strategic product, technical architecture, and live presentation script for RootCause AI's hackathon submission.

---

## 1. Live Presentation Script: The 2-Minute Demo

### **Slide 1: The Hook**
> *"Every monitoring system can tell you that something is broken. Grafana turns red, Slack alerts fire, and pager calls wake up SREs. But who investigates WHY?"*
> 
> *"Traditional observability stops at detection. SREs then spend hours matching logs, reading git histories, recreating environments, and guessing root causes. Today, we are introducing RootCause AI: the world's first autonomous AI failure-investigation and verification agent."*

### **Slide 2: Live Demo Sequence (The Killer Moment)**
1.  **Dashboard Normal State**: 
    Show the healthy classification system.
    *   *Accuracy*: 94.2%
    *   *Latency*: 180 ms
    *   *Error Rate*: 0.4%
2.  **Trigger Failure (Inject Scenario #104)**:
    Click the **[#104 Preprocessing]** button in the top toolbar to simulate a production deployment.
    *   30 seconds later, the screen turns red.
    *   *Accuracy drops to 71.3%*, *latency remains 180ms*, *error rate spikes to 17.8%*.
3.  **Click [INVESTIGATE WITH ROOTCAUSE AI]**:
    *   The agent immediately starts working. Watch the timeline update live.
    *   **Triage**: Classifies the failure as an ML Accuracy Degradation. Scans git commits and notes deployment DEP-401 occurred 18 minutes prior.
    *   **Competing Hypotheses**: Generates 4 active hypotheses.
        *   H1: Data Drift (25%)
        *   H2: Wrong Model Version (20%)
        *   H3: Preprocessing Normalization Mismatch (45%)
        *   H4: Dependency Upgrade (10%)
    *   **Experiment Action**: Planner decides: *"Comparing preprocessing normalization scales will yield the highest information gain."* It writes a Python script and executes it in the sandbox.
    *   **Belief Shift**: The experiment output returns `PREPROCESSING_MISMATCH: TRUE`. In real-time, the Recharts graph shifts: **H3 surges from 45% to 95%**; H1 and H2 crash to <5% (Falsified).
    *   **Isolated Reproduction**: The agent spins up a sandbox replica, runs the pre-deployment code vs post-deployment code, and reproduces the 71.3% accuracy drop exactly.
    *   **Patch Proposal**: The agent proposes a Git patch to revert standard scaling back to MinMax normalization.
    *   **Human-in-the-Loop**: The UI flashes yellow. The agent halts and requests approval: *"Proposed patch will recover validation accuracy to 93.9%. Click to approve production rollout."*
4.  **Click [APPROVE PRODUCTION HOTFIX PATCH]**:
    *   The agent applies the patch, runs the regression suite in the sandbox, verifies accuracy is restored, deploys, and resets the simulator metrics to healthy.
    *   *Accuracy recovers to 94.2%*. Telemetry returns to green.

---

## 2. Product Strategy & Positioning

### **Problem Statement**
Modern microservice and ML applications fail silently and in complex, multi-dimensional ways. Monitoring dashboards alert on symptoms (e.g. "Accuracy dropped") but cannot diagnose causes. SREs waste critical hours correlating events, digging through logs, and manually writing code to test hypotheses.

### **Target Users**
*   **DevOps / SRE Teams**: Who want to automate incident triaging, evidence gathering, and rollback verification.
*   **MLOps Engineers**: Who need to diagnose silent mathematical regressions (e.g., data drift, scaling mismatches, dependency precision changes) that standard APM logs miss.

### **Why an Agentic Solution is Necessary**
A standard chatbot or RAG search can only summarize log lines. They cannot:
1.  **Formulate and test hypotheses** under uncertainty.
2.  **Interact with systems** dynamically to run experiments.
3.  **Verify assumptions** inside isolated sandbox containers.
4.  **Confirm solutions** using empirical testing before touching production code.
RootCause AI behaves like a junior SRE: it queries telemetry, runs diagnostic code, and rollback-tests patches.

---

## 3. Competitive Differentiation

| Capability | Traditional APM (Datadog / Prometheus) | RAG Observability Chatbots | RootCause AI |
| :--- | :--- | :--- | :--- |
| **Alerting** | ✅ Real-time metric alerts | ❌ Passive | ✅ Auto Alert Ingestion |
| **Root Cause Analysis** | ❌ Manual correlation required | ❌ Text summarizing only | ✅ Bayesian Hypothesis Ranking |
| **Code Execution** | ❌ None | ❌ None | ✅ Isolated Docker Sandboxes |
| **Failure Reproduction** | ❌ None | ❌ None | ✅ Workspace Replica Execution |
| **Fix Verification** | ❌ Manual SRE verification | ❌ Untested text recommendation | ✅ Automated patch regression tests |

---

## 4. Business Opportunity & Future Roadmap

### **Business Potential**
*   **Developer Productivity**: Decreases SRE triage labor by up to 90%.
*   **Mean Time to Resolution (MTTR)**: Drops critical production downtime from hours to under 2 minutes.
*   **Enterprise Integration**: Can be packaged as a GitHub Actions bot, a Slack notification integration, or an agent sidecar running inside Kubernetes clusters.

### **Future Roadmap**
*   **Phase 1 (Post-MVP)**: Integrate real-world Prometheus, Loki, OpenTelemetry, and GitHub API connections.
*   **Phase 2**: Add support for distributed system network failures, database lock issues, and cloud IAM permissions drift.
*   **Phase 3**: Multi-agent collaboration where specialized agents debug infrastructure, code quality, and database connection pools.
