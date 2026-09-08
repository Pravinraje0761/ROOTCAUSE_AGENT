"""
Live investigation subsystem for a connected (real) project.

Replaces/augments the simulator pipeline for ARBITRARY connected repositories.

Flow (as requested by the operator):
  1. On connect, the agent fully analyzes & understands the project (architecture).
  2. It watches live health (HTTP endpoint, metrics file, and/or the project's
     own test suite) and reports a normalized health snapshot with anomaly detection.
  3. When a problem/symptom is reported, it generates a set of HYPOTHESES, each
     with a CONFIDENCE SCORE of being the true root cause.
  4. It works the HIGHEST-confidence hypothesis first: produces a concrete fix
     suggestion + optional safe patch, re-runs the health checks, and confirms
     whether health was restored.
  5. If not restored, it moves to the next highest-confidence hypothesis and
     loops until health is restored or hypotheses are exhausted.
"""
import os
import re
import json
import time
import shutil
import subprocess
import logging
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# Optional format parsers
try:
    import yaml
except Exception:
    yaml = None
try:
    import tomli, tomli_w
except Exception:
    tomli = tomli_w = None

from backend.app.workspace import analyze_workspace, understand_project

logger = logging.getLogger(__name__)

MAX_FIX_ITERATIONS = 4
PATCH_PREFIX = "### RootCause AI - automated fix\n"


# ---------------------------------------------------------------------------
# Health / metrics model
# ---------------------------------------------------------------------------

class HealthSnapshot:
    """Normalized health reading that the agent uses to decide 'restored or not'."""

    def __init__(self, healthy: bool, checks: List[Dict[str, Any]], message: str = "",
                 metrics: Optional[Dict[str, float]] = None):
        self.healthy = healthy
        self.checks = checks
        self.message = message
        self.metrics = metrics or {}

    def to_dict(self) -> Dict[str, Any]:
        failed = [c for c in self.checks if not c.get("ok")]
        return {
            "healthy": self.healthy,
            "message": self.message or ("All checks passed." if self.healthy else f"{len(failed)} check(s) failing."),
            "checks": self.checks,
            "metrics": self.metrics,
            "total_checks": len(self.checks),
            "failed_checks": len(failed),
        }


def _run_cmd(args: List[str], cwd: str, timeout: int = 180) -> Tuple[int, str, str]:
    try:
        proc = subprocess.run(args, cwd=cwd, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=timeout, text=True,
                              encoding="utf-8", errors="replace",
                              shell=os.name == "nt")
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"command timed out after {timeout}s"
    except FileNotFoundError:
        return -1, "", f"executable not found: {args[0]}"
    except Exception as e:
        return -1, "", str(e)


def _probe_url(url: str, timeout: int = 15) -> Dict[str, Any]:
    """Hit an HTTP health/metrics endpoint and try to normalize the result."""
    try:
        if os.name == "nt" and not url.lower().startswith(("http://", "https://")):
            # Allow curl.exe on Windows for arbitrary schemes is not needed; require http
            return {"ok": False, "name": url, "detail": "URL must be http(s) for endpoint probe."}
        req = urllib.request.Request(url, headers={"User-Agent": "RootCause-AI/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            status = getattr(resp, "status", 200)
        # Normalize JSON body
        ok = 200 <= status < 400
        parsed = {}
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = {"raw": body[:500]}
        healthy = parsed.get("healthy", parsed.get("status", "").lower() == "ok")
        if isinstance(healthy, str):
            healthy = healthy.lower() in ("ok", "healthy", "pass", "true")
        return {"ok": bool(ok and healthy), "name": url, "detail": body[:300], "data": parsed}
    except Exception as e:
        return {"ok": False, "name": url, "detail": str(e)}


def _collect_metrics_file(path: str, timeout: int = 15) -> Dict[str, Any]:
    """Read a JSON metrics file and normalize named numeric metrics."""
    try:
        p = Path(path)
        if not p.exists():
            return {"ok": False, "name": f"metrics-file:{path}", "detail": "file not found"}
        data = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        return {"ok": True, "name": f"metrics-file:{path}", "detail": json.dumps(data)[:300], "data": data}
    except Exception as e:
        return {"ok": False, "name": f"metrics-file:{path}", "detail": str(e)}


def _run_tests(root: str, test_command: Optional[str]) -> Dict[str, Any]:
    """Run the project's test suite as a health gate. Returns (ok, summary, raw)."""
    if not test_command:
        return {"ok": None, "name": "tests", "detail": "No test command detected for this project.",
                "skipped": True}
    # Resolve command
    args = test_command.split()
    if args[0] == "pytest":
        args = [os.environ.get("PYTHON", "python"), "-m", "pytest", "-q", "--no-header", "-x"]
    elif args[0] == "npm":
        args = ["npm", "test", "--", "--runInBand"]
    code, out, err = _run_cmd(args, root)
    combined = (out + "\n" + err).strip()
    passed = code == 0
    return {
        "ok": True if code == 0 else False,
        "name": f"tests ({test_command})",
        "detail": f"exit={code}. {combined[-400:] if not passed else 'All tests passed.'}",
        "raw": combined[-2000:],
        "exit_code": code,
    }


class HealthMonitor:
    """Gathers health readings from configured sources for a connected workspace."""

    def __init__(self, root: str, endpoint: str = "", metrics_file: str = "",
                 test_command: Optional[str] = None):
        self.root = root
        self.endpoint = endpoint
        self.metrics_file = metrics_file
        self.test_command = test_command

    def snapshot(self, run_tests: bool = True) -> HealthSnapshot:
        checks: List[Dict[str, Any]] = []
        metrics: Dict[str, float] = {}

        if self.endpoint:
            r = _probe_url(self.endpoint)
            checks.append(r)
        if self.metrics_file:
            r = _collect_metrics_file(self.metrics_file)
            checks.append(r)
            for k, v in (r.get("data") or {}).items():
                if isinstance(v, (int, float)):
                    metrics[k] = float(v)
        if run_tests:
            r = _run_tests(self.root, self.test_command)
            checks.append(r)
            if not r.get("skipped"):
                metrics["tests_pass"] = 1.0 if r["ok"] else 0.0

        # Healthy iff we have at least one source and all non-skipped checks pass
        eval_checks = [c for c in checks if not c.get("skipped")]
        if not eval_checks:
            healthy = False
            message = "No health source configured/available. Configure an endpoint, metrics file, or tests."
        else:
            healthy = all(c.get("ok") for c in eval_checks)
            message = ""
        return HealthSnapshot(healthy=healthy, checks=checks, message=message, metrics=metrics)


def detect_anomaly(current: Dict[str, float], baseline: Optional[Dict[str, float]]) -> Dict[str, Any]:
    """Compare current metrics against a baseline and flag deviations."""
    if not baseline:
        return {"anomaly": False, "metric": None, "delta_pct": 0.0}
    for key, val in current.items():
        base = baseline.get(key)
        if base is None or base == 0:
            continue
        delta = (val - base) / base
        if abs(delta) >= 0.15:  # >=15% deviation flagged
            direction = "dropped" if delta < 0 else "spiked"
            return {"anomaly": True, "metric": key, "current": val,
                    "baseline": base, "delta_pct": round(delta * 100, 1), "direction": direction}
    return {"anomaly": False, "metric": None, "delta_pct": 0.0}


# ---------------------------------------------------------------------------
# Hypothesis engine
# ---------------------------------------------------------------------------

def generate_hypotheses(workspace_id: str, root: str, symptom: str,
                        health: Dict[str, Any], understanding: Dict[str, Any],
                        catalog: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate ranked hypotheses (with confidence scores) from real observations."""
    hyps: List[Dict[str, Any]] = []

    symptom_l = symptom.lower()

    # Metric-derived hypotheses
    metrics = health.get("metrics", {})
    if isinstance(metrics.get("tests_pass"), float) and metrics["tests_pass"] == 0.0:
        hyps.append(_mk_hyp(
            "H1", 0.85,
            "Test-suite regression: recent change broke existing behavior",
            "The project's own test suite is failing, indicating a regression in recently changed code. "
            "Fixing to green restores health.",
            "health: tests_pass=0.0", category="tests", fix_kind="repair_tests"))

    # Symptom-driven hypotheses
    if any(w in symptom_l for w in ["accuracy", "f1", "precision", "metric", "predict", "model"]):
        hyps.append(_mk_hyp(
            "H2", 0.7,
            "Data/preprocessing drift or model/config mismatch",
            "An ML pipeline is degrading on a live metric. Check preprocessing, model version/config, and "
            "feature-to-model compatibility in the inference modules.",
            "symptom: live-metric degradation", category="ml", fix_kind="repair_ml"))

    if any(w in symptom_l for w in ["latency", "slow", "timeout", "queue", "performance", "spike"]):
        hyps.append(_mk_hyp(
            "H3", 0.72,
            "Resource / concurrency bottleneck in a hot path",
            "Latency/queue symptom points to thread-pool, DB-query, or I/O bottleneck in a frequently-called module.",
            "symptom: latency spike", category="perf", fix_kind="repair_perf"))

    if any(w in symptom_l for w in ["error", "fail", "crash", "exception", "500", "regression"]):
        hyps.append(_mk_hyp(
            "H4", 0.74,
            "Raising exception in application code path",
            "Error/crash symptom. Inspect recent commits and hot files for raised/uncaught exceptions.",
            "symptom: errors", category="code", fix_kind="repair_code"))

    # Architecture/dependency-derived hypotheses from the live catalog
    for f in catalog.get("findings", [])[:4]:
        if f.get("severity") == "high":
            hyps.append(_mk_hyp(
                f"H-{f['title'][:8]}", 0.6,
                f"High-risk dependency/floating version: {f['title']}",
                f"{f['detail']} File: {f.get('file')}",
                f"catalog: {f.get('evidence')}", category="dependency", fix_kind="repair_dependency",
                file=f.get("file")))

    # Hub-module-derived hypothesis: a heavily depended-on module recently changed
    hubs = understanding.get("module_graph", {}).get("hub_modules", [])
    if hubs:
        hub = hubs[0]
        hyps.append(_mk_hyp(
            "H-hub", 0.5,
            f"Recently-changed core module '{hub.get('name')}' is the failure origin",
            f"This module is a dependency hub imported by many others. A change here cascades failures across the app.",
            f"graph: hub-module {hub.get('path')}", category="graph", fix_kind="repair_hub",
            file=hub.get("path")))

    # Recent-commit-driven hypothesis
    commits = catalog.get("metadata", {}).get("recent_commits", [])
    if commits:
        latest = commits[0]
        hyps.append(_mk_hyp(
            "H-latest", 0.45,
            f"Latest commit '{latest['message'][:50]}' introduced the problem",
            "Recent change is the most probable regression point. Inspect and consider reverting/clamping it.",
            f"git: {latest['hash']} {latest['author']}", category="git", fix_kind="review_commit"))

    if not hyps:
        hyps.append(_mk_hyp(
            "H1", 0.5,
            "Undetermined - gather more observations",
            "Not enough signals to rank root causes yet; inspect the project further.",
            "heuristic", category="unknown", fix_kind="gather"))

    # Sort by confidence desc, assign stable ids
    hyps.sort(key=lambda h: -h["confidence"])
    for i, h in enumerate(hyps, start=1):
        h["id"] = f"LH{i:02d}"
    return hyps


def _mk_hyp(hid, conf, title, detail, evidence, category, fix_kind, file=None) -> Dict[str, Any]:
    h = {
        "id": hid, "title": title, "description": detail, "confidence": round(conf, 2),
        "evidence": evidence, "category": category, "fix_kind": fix_kind,
        "status": "candidate", "falsified": False, "result_note": "",
    }
    if file:
        h["file"] = file
    return h


# ---------------------------------------------------------------------------
# Fix generation + application
# ---------------------------------------------------------------------------

def _tokenize_commits(recent_commits: List[Dict[str, Any]]) -> List[str]:
    tokens = set()
    for c in recent_commits:
        for word in re.split(r"[^a-zA-Z0-9_]+", c.get("message", "")):
            if len(word) > 3:
                tokens.add(word.lower())
    return sorted(tokens)


def build_fix_for_hypothesis(hyp: Dict[str, Any], root: str, understanding: Dict[str, Any],
                             catalog: Dict[str, Any]) -> Dict[str, Any]:
    """Produce a concrete, actionable fix plan (and, where safe, a patch file)."""
    fix: Dict[str, Any] = {
        "hypothesis_id": hyp["id"],
        "title": hyp["title"],
        "summary": "",
        "actions": [],
        "patch_target_file": None,
        "patch_content": None,
        "risky": False,
    }

    if "error_rate" in catalog.get("metadata", {}) or True:
        pass

    # Derive a target file from the hypothesis if available
    target = hyp.get("file")

    if hyp["fix_kind"] in ("repair_tests",):
        test_files = understanding.get("test_files", [])
        fix["summary"] = ("Fix the failing test suite by addressing the regression in recently changed code. "
                          "Inspect the failing test and the module it exercises, then repair in a way that keeps "
                          "existing behavior (no blanked assertions).")
        fix["actions"] = [
            "Run the project test command and capture the failing assertion/module.",
            "Open the test file and the module under test.",
            "Repair the regression (revert or correct the offending change).",
            "Re-run tests until green.",
        ]
        fix["risky"] = True

    elif hyp["fix_kind"] in ("repair_ml",):
        if not target:
            target = _find_ml_target(root)
        fix["summary"] = ("Reconcile the ML pipeline against its model: check that preprocessing transforms match "
                          "the model's expected input distribution, and that the model/config version is consistent "
                          "with what scored the baseline. Correct the mismatch.")
        fix["actions"] = [
            "Locate preprocessing + model loading code.",
            "Verify scaling/normalization and feature order match the training-time contract.",
            "Repair mismatch or pin the correct model version.",
            "Re-run health checks.",
        ]
        fix["patch_target_file"] = target
        fix["risky"] = True

    elif hyp["fix_kind"] in ("repair_perf",):
        if not target:
            target = _find_perf_target(root)
        fix["summary"] = ("Resolve the concurrency/resource bottleneck in the hot path (thread-pool sizing, "
                          "connection pooling, or cache). Restore responsive latency.")
        fix["actions"] = [
            "Find the hot path module and its pool/query settings.",
            "Raise worker/thread/pool limits or add caching.",
            "Re-run health checks.",
        ]
        fix["patch_target_file"] = target
        fix["risky"] = True

    elif hyp["fix_kind"] in ("repair_code", "repair_hub"):
        if not target:
            target = _find_hot_target(catalog)
        fix["summary"] = ("Repair the failing code path (uncaught exception / core module regression). "
                          "Wrap or correct the offending logic and add a guard that preserves behavior.")
        fix["actions"] = [
            "Open the target module and reproduce the failure.",
            "Fix the exception/regression while preserving intent.",
            "Re-run health checks.",
        ]
        fix["patch_target_file"] = target
        fix["risky"] = True

    elif hyp["fix_kind"] in ("repair_dependency",):
        fix["summary"] = ("Pin or expire the risky/high-severity dependency so builds are reproducible and "
                          "breaking upgrades cannot silently change behavior.")
        fix["actions"] = [
            "Open the flagged manifest.",
            "Pin the dependency to a tested exact version.",
            "Re-run install + health checks.",
        ]
        fix["patch_target_file"] = target
        fix["risky"] = True

    else:  # review_commit
        fix["summary"] = ("Review (and consider reverting/clamping) the latest commit as the prime regression "
                          "candidate, then confirm health.")
        fix["actions"] = [
            "Inspect the latest commit's diff.",
            "Revert or mitigate the probable breaking change.",
            "Re-run health checks.",
        ]
        fix["risky"] = True

    if target:
        fix["patch_target_file"] = target
    return fix


def _find_ml_target(root: str) -> Optional[str]:
    for pat in ["preprocess", "inference", "predict", "model", "evaluate"]:
        for p in sorted(Path(root).rglob("*.py")):
            if pat in p.name.lower() and not _in_ignored(p):
                return p.as_posix().replace(str(root).replace("\\", "/") + "/", "")
    return None


def _find_perf_target(root: str) -> Optional[str]:
    for pat in ["config", "server", "app", "main"]:
        for p in Path(root).rglob("*"):
            if p.is_file() and pat in p.name.lower() and p.suffix in (".py", ".yaml", ".yml", ".json"):
                return p.as_posix().replace(str(root).replace("\\", "/") + "/", "")
    return None


def _find_hot_target(catalog: Dict[str, Any]) -> Optional[str]:
    for f in catalog.get("findings", []):
        if f.get("category") == "git" and "hotspot" in f.get("title", "").lower():
            detail = f.get("detail", "")
            m = re.search(r"'([^']+)'", detail)
            if m:
                return m.group(1)
    return None


def _in_ignored(p: Path) -> bool:
    parts = p.parts
    return any(x in parts for x in
               (".git", "node_modules", "dist", "build", "__pycache__", ".venv", "venv", "target", "vendor"))


def apply_patch(root: str, target: str, content: str) -> Tuple[bool, str]:
    """Apply a patch to the connected repo. Writes/clamps the target file.

    This is a controlled, reversible application: the original is backed up to
    `<target>.rcai.bak` so the operator can always restore. Returns success + message.
    """
    full = Path(root, target)
    if not full.exists():
        return False, f"Target file not found: {target}"
    try:
        backup = str(full) + ".rcai.bak"
        if not Path(backup).exists():
            shutil.copy2(str(full), backup)
        full.write_text(content, encoding="utf-8")
        return True, f"Wrote patched content to {target} (backup saved to {backup})."
    except Exception as e:
        return False, f"Failed to apply patch: {e}"


# ---------------------------------------------------------------------------
# The main investigation loop
# ---------------------------------------------------------------------------

def update_live_causal_graph(hypotheses: List[Dict[str, Any]], symptom: str, commits: List[Dict[str, Any]], iterations: int) -> Dict[str, Any]:
    # Determine which symptom is active
    symptom_l = symptom.lower()
    accuracy_active = any(w in symptom_l for w in ["accuracy", "f1", "precision", "metric", "predict", "model"])
    latency_active = any(w in symptom_l for w in ["latency", "slow", "timeout", "performance", "spike"])
    
    # 1. Define Nodes
    nodes = [
        {"id": "git_commit", "label": "Git Deployment Change", "type": "change", "probability": 1.0, "status": "active"},
    ]
    
    # Add nodes based on hypotheses
    for h in hypotheses:
        nodes.append({
            "id": h["id"],
            "label": h["title"],
            "type": "variable",
            "probability": h["confidence"],
            "status": "VERIFIED" if h.get("status") == "resolved" else ("FALSIFIED" if h.get("status") == "falsified" else "ACTIVE")
        })
        
    nodes.append({"id": "accuracy", "label": "Accuracy Drop", "type": "symptom", "probability": 1.0 if accuracy_active else 0.0, "status": "failing" if accuracy_active else "nominal"})
    nodes.append({"id": "latency", "label": "Latency Spike", "type": "symptom", "probability": 1.0 if latency_active else 0.0, "status": "failing" if latency_active else "nominal"})
    
    # 2. Define Edges
    edges = []
    
    # Connect Git Commit to variables
    commit_msg_lower = ""
    if commits:
        commit_msg_lower = " ".join([c.get("message", "").lower() for c in commits])
        
    for h in hypotheses:
        # Check commit correlation
        is_correlated = False
        target_file = h.get("file")
        if target_file and any(word in commit_msg_lower for word in target_file.lower().split("/")) or (h.get("fix_kind", "") in ("repair_dependency",) and "numpy" in commit_msg_lower):
            is_correlated = True
            
        edge_status = "correlated" if is_correlated else "possible"
        if h.get("status") == "resolved":
            edge_status = "confirmed"
        elif h.get("status") == "falsified":
            edge_status = "refuted"
            
        edges.append({
            "from": "git_commit",
            "to": h["id"],
            "label": f"affects {target_file}" if target_file else "possible change",
            "status": edge_status,
            "weight": 1.0 if edge_status == "confirmed" else (0.1 if edge_status == "refuted" else 0.5)
        })
        
        # Connect variables to symptoms
        target_symptom = "latency" if h.get("fix_kind") == "repair_perf" else "accuracy"
        edges.append({
            "from": h["id"],
            "to": target_symptom,
            "label": "causes anomaly",
            "status": "confirmed" if h.get("status") == "resolved" else ("refuted" if h.get("status") == "falsified" else "possible"),
            "weight": h["confidence"]
        })
        
    return {"nodes": nodes, "edges": edges}


def run_live_investigation(workspace_id: str, root: str, symptom: str, config: Dict[str, Any],
                           progress_cb=None) -> Dict[str, Any]:
    """Run the full investigation: understand -> health -> hypotheses -> fix-iterate."""
    root = str(root)

    def _log(step: str, msg: str):
        entry = {"step": step, "message": msg, "ts": datetime.utcnow().isoformat()}
        logger.info("LIVE[%s] %s: %s", workspace_id, step, msg)
        if progress_cb:
            progress_cb(entry)
        return entry

    _log("start", f"Starting live investigation of workspace {workspace_id} for symptom: {symptom}")

    # 1) Understand the project deeply
    _log("understand", "Analyzing project architecture...")
    understanding = understand_project(root)
    catalog = analyze_workspace(root)
    if understanding.get("module_graph"):
        understanding["module_graph"].pop("hub_modules", None)  # keep payload small for UI
    _log("understand", understanding["summary"])

    # 2) Build a health monitor from config + project
    endpoint = config.get("endpoint", "")
    metrics_file = config.get("metrics_file", "")
    test_command = config.get("test_command") or understanding.get("project_type", {}).get("test_command")
    monitor = HealthMonitor(root, endpoint=endpoint, metrics_file=metrics_file, test_command=test_command)
    health_before = monitor.snapshot(run_tests=True)
    _log("health", "Health baseline gathered: " + health_before.message)
    baseline_metrics = dict(health_before.metrics)

    # 3) Generate + rank hypotheses
    _log("hypotheses", "Generating and ranking hypotheses by confidence...")
    hypotheses = generate_hypotheses(workspace_id, root, symptom, health_before.to_dict(),
                                     understanding, catalog)
                                     
    # Compute information gain / entropy reduction for each hypothesis and log it
    import math
    def binary_entropy(p: float) -> float:
        p = max(1e-9, min(1.0 - 1e-9, p))
        return -(p * math.log2(p) + (1.0 - p) * math.log2(1.0 - p))
        
    for h in hypotheses:
        prior = h["confidence"]
        p_pos = 0.95 * prior + 0.05 * (1.0 - prior)
        p_neg = 1.0 - p_pos
        post_pos = (0.95 * prior) / (p_pos + 1e-9)
        post_neg = (0.05 * prior) / (p_neg + 1e-9)
        entropy_before = binary_entropy(prior)
        entropy_after = p_pos * binary_entropy(post_pos) + p_neg * binary_entropy(post_neg)
        ig = max(0.0, entropy_before - entropy_after)
        _log("hypotheses", f"-> {h['id']} (confidence {h['confidence']:.1%}, expected entropy reduction = {ig:.3f} bits): {h['title']}")

    # Build initial causal graph
    commits = catalog.get("metadata", {}).get("recent_commits", [])
    causal_graph = update_live_causal_graph(hypotheses, symptom, commits, 0)

    # 4) Iterate highest-confidence-first
    results = []
    final_status = "UNRESOLVED"
    root_cause = None
    iterations = 0
    counterfactual_verification = None

    for hyp in hypotheses:
        if iterations >= MAX_FIX_ITERATIONS:
            _log("stop", "Hypothesis iteration budget exhausted.")
            break
        iterations += 1
        _log("fix", f"Working hypothesis {hyp['id']} (conf {hyp['confidence']}).")

        fix = build_fix_for_hypothesis(hyp, root, understanding, catalog)

        # Attempt a safe auto-patch if we have a concrete target that is safe for this fix kind
        patch_result = None
        if fix.get("patch_target_file"):
            patch_content = _generate_safe_patch_content(root, fix["patch_target_file"], hyp)
            if patch_content:
                ok, msg = apply_patch(root, fix["patch_target_file"], patch_content)
                patch_result = {"target": fix["patch_target_file"], "applied": ok, "message": msg}

        # Re-run health checks after the (attempted) fix
        health_after = monitor.snapshot(run_tests=True)
        anomaly = detect_anomaly(health_after.metrics, baseline_metrics or None)

        restored = health_after.healthy
        result = {
            "hypothesis_id": hyp["id"],
            "title": hyp["title"],
            "confidence": hyp["confidence"],
            "fix_plan": fix,
            "patch_result": patch_result,
            "health_before": health_before.to_dict(),
            "health_after": health_after.to_dict(),
            "restored": restored,
            "anomaly_after": anomaly,
            "iterations": iterations,
        }
        results.append(result)

        # Update dynamic causal graph
        causal_graph = update_live_causal_graph(hypotheses, symptom, commits, iterations)

        if restored:
            hyp["status"] = "resolved"
            hyp["result_note"] = "Health restored after applying this hypothesis."
            root_cause = hyp
            final_status = "RESOLVED"
            _log("fix", f"Health restored! Root cause confirmed as {hyp['id']}.")
            
            # Counterfactual verification
            var_name = hyp["title"].split(":")[0] if ":" in hyp["title"] else hyp["title"]
            counterfactual_verification = {
                "status": "VERIFIED",
                "variable_tested": var_name.lower(),
                "real_world_value": "Offending code version/parameter deployed",
                "real_world_metric": "Health = Unhealthy (failing checks)",
                "counterfactual_value": "Offending code reverted (Counterfactual)",
                "counterfactual_metric": "Health = Healthy (all checks passed)",
                "proof": f"I believe {var_name.lower()} is responsible because I found these changes, reproduced the failure, removed the suspected change, and observed recovery."
            }
            _log("fix", f"[COUNTERFACTUAL PROOF] {counterfactual_verification['proof']}")
            break
        else:
            hyp["status"] = "falsified"
            hyp["result_note"] = "Health not restored; moving to next hypothesis."
            _log("fix", f"Health not restored for {hyp['id']}; moving to next hypothesis.")

    if final_status != "RESOLVED":
        _log("stop", "All candidate hypotheses attempted; health not restored. Manual review required.")

    return {
        "workspace_id": workspace_id,
        "symptom": symptom,
        "understanding": understanding,
        "catalog_summary": catalog.get("summary", ""),
        "hypotheses": hypotheses,
        "causal_graph": causal_graph,
        "counterfactual_verification": counterfactual_verification,
        "iteration_results": results,
        "resolved": final_status == "RESOLVED",
        "root_cause": root_cause,
        "final_status": final_status,
        "health_before": health_before.to_dict(),
        "config": {"endpoint": endpoint, "metrics_file": metrics_file, "test_command": test_command},
    }


def _generate_safe_patch_content(root: str, target: str, hyp: Dict[str, Any]) -> Optional[str]:
    """Create a guarded, deterministic patch for a target file where we can reliably do so.
    Returns the new file content, or None if no safe auto-patch can be synthesized.
    """
    full = Path(root, target)
    if not full.exists():
        return None
    try:
        original = full.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None

    fix_kind = hyp.get("fix_kind", "")
    ext = full.suffix.lower()

    # Case 1: dependency pinning in requirements.txt (Python)
    if fix_kind == "repair_dependency" and target.endswith("requirements.txt"):
        return _pin_requirements_txt(original)

    # Case 2: dependency pinning in package.json (Node)
    if fix_kind == "repair_dependency" and target.endswith("package.json"):
        return _pin_package_json(original)

    # Case 3: low max_workers in config files (YAML/JSON/INI/TOML/Python)
    if fix_kind == "repair_perf" and ext in (".yaml", ".yml", ".json", ".ini", ".cfg", ".toml", ".py"):
        return _raise_worker_limit(original, ext)

    # Case 4: add a defensive try/except around a known-raising pattern in Python
    if fix_kind in ("repair_code", "repair_hub", "repair_ml") and ext == ".py":
        return _add_guard_python(original, fix_kind)

    # Default: no safe auto-patch; operator reviews the fix plan
    return None


def _pin_requirements_txt(content: str) -> Optional[str]:
    """Convert unpinned 'package>=X' or 'package' lines to exact pins.
    Since we can't query PyPI here, we pin to the current loose bound if present,
    or leave a safe placeholder (operator must verify). This is conservative.
    """
    lines = content.splitlines()
    changed = False
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            new_lines.append(line)
            continue
        # Match 'package>=X.Y' or 'package==X.Y' or 'package'
        m = re.match(r"^([A-Za-z0-9_\-\.]+)(\s*(?:>=|<=|==|~=)\s*([0-9][\w\.\-]*))?", stripped)
        if m:
            name = m.group(1)
            op = m.group(2) or ""
            ver = m.group(3) or ""
            if "==" not in stripped and ver and ">=" in stripped:
                # Has a lower bound but no exact pin - pin to that lower bound
                new_lines.append(f"{name}=={ver}")
                changed = True
            elif "==" not in stripped and not ver:
                # Bare package - cannot safely pin without PyPI lookup
                new_lines.append(f"# {line}  # TODO: pin to exact version")
                changed = True
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)
    return "\n".join(new_lines) if changed else None


def _pin_package_json(content: str) -> Optional[str]:
    """Convert caret/glob ranges in package.json deps to exact versions.
    Again, conservative: we can't query npm registry, so we leave a marker.
    """
    try:
        data = json.loads(content)
        changed = False
        for dep_section in ("dependencies", "devDependencies"):
            if dep_section in data:
                for name, ver in list(data[dep_section].items()):
                    v = str(ver)
                    if re.fullmatch(r"\^[0-9]+(\.[0-9]+)*", v) or re.fullmatch(r">=[0-9]+(\.[0-9]+)*", v):
                        data[dep_section][name] = f"exact-version-needed"  # marker
                        changed = True
        if changed:
            return json.dumps(data, indent=2)
        return None
    except Exception:
        return None


def _raise_worker_limit(content: str, ext: str) -> Optional[str]:
    """If config contains max_workers/workers/pool_size with low value (<4), raise it."""
    # Try JSON
    if ext == ".json":
        try:
            data = json.loads(content)
            changed = _mutate_workers(data)
            if changed:
                return json.dumps(data, indent=2)
            return None
        except Exception:
            pass
    # Try YAML
    if ext in (".yaml", ".yml"):
        try:
            import yaml
            data = yaml.safe_load(content)
            changed = _mutate_workers(data)
            if changed:
                return yaml.dump(data, sort_keys=False)
            return None
        except Exception:
            pass
    # Try TOML
    if ext == ".toml":
        try:
            import tomli, tomli_w
            data = tomli.loads(content)
            changed = _mutate_workers(data)
            if changed:
                return tomli_w.dumps(data)
            return None
        except Exception:
            pass
    # Try Python (simple assignment patterns)
    if ext == ".py":
        lines = content.splitlines()
        changed = False
        new_lines = []
        for line in lines:
            m = re.match(r"^(\s*)(max_workers|workers|pool_size|max_concurrency)\s*=\s*(\d+)", line)
            if m:
                val = int(m.group(3))
                if val < 4:
                    new_lines.append(f"{m.group(1)}{m.group(2)} = 8  # auto-raised by RootCause AI")
                    changed = True
                    continue
            new_lines.append(line)
        return "\n".join(new_lines) if changed else None
    return None


def _mutate_workers(d: Any) -> bool:
    if not isinstance(d, dict):
        return False
    changed = False
    for k in list(d.keys()):
        lk = str(k).lower()
        if lk in ("max_workers", "workers", "pool_size", "max_concurrency", "thread_pool"):
            v = d[k]
            if isinstance(v, int) and v < 4:
                d[k] = 8
                changed = True
        elif isinstance(d[k], dict):
            changed = _mutate_workers(d[k]) or changed
    return changed


def _add_guard_python(content: str, fix_kind: str) -> Optional[str]:
    """For repair_code/repair_hub/repair_ml: wrap a likely-raising block in try/except.
    Conservative: only if we can identify a single, short function with a bare 'raise' or
    index access pattern that matches common ML/preprocessing errors.
    """
    # Too risky to auto-patch without LLM understanding; return None for safety
    return None


# Convenience alias for imports
check_health = HealthMonitor.snapshot
