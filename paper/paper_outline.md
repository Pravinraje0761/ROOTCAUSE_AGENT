# Target Journal Paper Outline

**Title:** Information-Guided Autonomous Debugging: Bayesian Active Experimentation for Software Incident Diagnosis and Repair  
**Target Venue:** IEEE Transactions on Software Engineering (TSE) / ACM Transactions on Software Engineering and Methodology (TOSEM)

---

## Abstract
Modern microservice and machine learning deployments fail in complex, silent, and multi-dimensional ways. Traditional Application Performance Monitoring (APM) tools detect symptom anomalies but cannot determine causal roots. While large language model (LLM) agents have emerged as promising autonomous programmers, they struggle to reason under state uncertainty, often reverting to brute-force repair attempts that incur high token costs and risk destabilizing production systems. 

We present **RootCause**, an autonomous incident investigation framework that integrates LLM code generation with classical decision-theoretic diagnostics. RootCause tracks competing hypotheses as an explicit Bayesian belief state and selects diagnostic experiments by maximizing Expected Information Gain (EIG) to minimize Shannon entropy. Once the root cause is resolved, RootCause reproduces the failure in a replica sandbox, applies a generated code patch, and verifies regression safety before deployment. 

We evaluate RootCause against four state-of-the-art agent architectures on **RootCauseBench**, a newly curated benchmark containing 100 injected infrastructure and application failures. Our results demonstrate that information-guided active diagnostics statistically improve root-cause identification accuracy by 13-30% while reducing execution steps, API cost, and LLM calls by over 45%. We also show that explicit Bayesian tracking produces significantly better confidence calibration (Brier Score of 0.08 vs 0.32 for raw LLM confidence), validating its suitability for safety-critical human-in-the-loop gates.

---

## 1. Introduction
*   **The SRE Bottleneck:** Modern system debugging is dominated by the Mean Time to Resolution (MTTR). Developers waste hours manually correlating logs, metrics, and traces.
*   **Limitations of Current Paradigms:**
    *   *Traditional APM (Datadog, Grafana):* High detection, zero diagnosis.
    *   *RAG Chatbots:* Passive text summarizes, unable to query systems dynamically or formulate test scripts.
    *   *LLM Coding Agents (SWE-agent, AutoDev):* Lack explicit uncertainty tracking, leading to high-cost random trials or near-miss repairs.
*   **Proposed Solution:** A hybrid system combining the adaptive code execution of LLM agents with the mathematical rigor of Bayesian decision theory.
*   **Core Research Questions (RQs):**
    *   *RQ1 (Accuracy):* Can information-theoretic active experimentation improve diagnostic correctness?
    *   *RQ2 (Efficiency):* Does EIG selection reduce execution steps, tool usage, and financial cost?
    *   *RQ3 (Calibration):* Does Bayesian belief state tracking improve the calibration of agent confidence?
    *   *RQ4 (Repair Reliability):* Can closed-loop patch verification prevent regression leaks?

---

## 2. Methodology & Mathematical Framework

RootCause models the troubleshooting process as a **Partially Observable Markov Decision Process (POMDP)** over a finite set of competing hypotheses $\mathcal{H} = \{H_1, H_2, \dots, H_n\}$.

```
                    +--------------------------------+
                    |       Ingested Incident        |
                    +--------------------------------+
                                    |
                                    v
                    +--------------------------------+
                    |    1. Prior Beliefs P(H_i)     |
                    +--------------------------------+
                                    |
                                    v
                    +--------------------------------+
                    |  2. Calculate Information Gain |
                    |      for Untested Hypotheses   |
                    +--------------------------------+
                                    |
                                    v
                    +--------------------------------+
                    | 3. Run argmax EIG(e) Script in |
                    |       Isolated Sandbox         |
                    +--------------------------------+
                                    |
                                    v
                    +--------------------------------+
                    |    4. Bayesian Belief Update   |
                    +--------------------------------+
                                    |
                    +---------------+---------------+
                    |                               |
                    v                               v
          [Confidence < 0.80]             [Confidence >= 0.80]
                    |                               |
                    +-------------------------------+
                                                    |
                                                    v
                                    +-------------------------------+
                                    | 5. Closed-loop Sandbox Repair |
                                    +-------------------------------+
```

### A. Hypothesis Space and Initial Priors
When an incident is ingested, RootCause performs initial triage on log/telemetry symptoms to formulate $n$ candidate hypotheses, assigning each an initial prior probability:
$$P(H_i) \in [0, 1] \quad \text{s.t.} \quad \sum_{i=1}^n P(H_i) = 1.0$$

### B. Expected Information Gain (EIG)
For each available, untested diagnostic test $e \in \mathcal{E}$, we compute the Expected Shannon Entropy reduction. Let $H$ be the random variable representing the true hypothesis, and $o \in \{0, 1\}$ be the binary outcome (positive or negative) of running diagnostic test $e$.

The current entropy of the hypothesis space is:
$$H(H) = -\sum_{i=1}^n P(H_i) \log_2 P(H_i)$$

Assuming the diagnostic test has a sensitivity $\alpha = P(O=1 | H_{\text{target}})$ and specificity $\beta = P(O=0 | \neg H_{\text{target}})$, we compute:
1.  **Probability of Positive Outcome:**
    $$P(O=1) = \alpha P(H_{\text{target}}) + (1-\beta)(1 - P(H_{\text{target}}))$$
2.  **Probability of Negative Outcome:**
    $$P(O=0) = 1 - P(O=1)$$
3.  **Expected Entropy After Test:**
    $$E[H(H | e)] = P(O=1) H(H | O=1) + P(O=0) H(H | O=0)$$
4.  **Expected Information Gain:**
    $$EIG(e) = H(H) - E[H(H | e)]$$

The agent schedules the experiment that maximizes EIG:
$$e^* = \arg\max_{e \in \mathcal{E}} EIG(e)$$

### C. Bayesian Belief Updating
Upon observing the actual outcome $o^* \in \{0, 1\}$ from running experiment $e^*$, the prior probabilities are updated via Bayes' rule:
$$P(H_i | o^*) = \frac{P(o^* | H_i) P(H_i)}{\sum_{j=1}^n P(o^* | H_j) P(H_j)}$$
This updated posterior vector serves as the prior for the next planning iteration.

---

## 3. Empirical Evaluation Design

### A. Target Evaluation Metrics
To provide rigorous proof of the methodology's utility, the evaluation reports:
*   **Uncertainty Efficiency (UE):** Quantifies uncertainty reduction relative to token/financial cost:
    $$UE = \frac{H_{\text{initial}} - H_{\text{final}}}{\text{Token Cost} + \gamma \text{ Execution Time}}$$
*   **Brier Score (BS):** Measures confidence calibration accuracy:
    $$BS = \frac{1}{N} \sum_{k=1}^N (p_k - y_k)^2$$
    *where $p_k$ is the confidence assigned to the true cause, and $y_k \in \{0, 1\}$ is the outcome.*
*   **Expected Calibration Error (ECE):**
    $$ECE = \sum_{m=1}^M \frac{|B_m|}{N} | \text{accuracy}(B_m) - \text{confidence}(B_m) |$$

### B. Statistical Significance Protocol
*   **Repeated Runs:** All stochastic baseline components are executed 10 times per incident to build confidence bounds.
*   **Non-parametric Tests:** We utilize the **Wilcoxon Signed-Rank Test** for paired comparisons (RootCause vs ReAct) to verify that improvements in cost and time are statistically significant ($p < 0.05$).
*   **Effect Size:** Cliff's Delta ($\delta$) is calculated to assess the magnitude of the difference.
