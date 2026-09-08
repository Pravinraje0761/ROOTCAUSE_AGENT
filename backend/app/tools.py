import logging
import random
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from backend.app.simulator import sim_state, GIT_HISTORY, DEPLOYMENT_HISTORY, generate_telemetry_history
from backend.app.sandbox import sandbox_manager

logger = logging.getLogger(__name__)

def get_metrics(metric_name: str, minutes_ago: int = 120) -> Dict[str, Any]:
    """
    Retrieves time-series metric data for the production API.
    Supported metric_name values: 'accuracy', 'latency', 'error_rate'
    """
    history = generate_telemetry_history(seconds_ago=minutes_ago * 60, interval_s=60)
    
    points = []
    for h in history:
        val = h.get(metric_name, 0.0)
        points.append({
            "timestamp": h["timestamp"],
            "value": val
        })
        
    if not points:
        return {"metric": metric_name, "points": [], "summary": {}}
        
    values = [p["value"] for p in points]
    current = values[-1]
    avg = sum(values) / len(values)
    
    return {
        "metric": metric_name,
        "points": points[-20:],  # return recent points for LLM context efficiency
        "summary": {
            "current": round(current, 4),
            "average": round(avg, 4),
            "max": round(max(values), 4),
            "min": round(min(values), 4),
            "unit": "seconds" if metric_name == "latency" else "ratio"
        }
    }

def get_logs(service: str, limit: int = 30) -> List[Dict[str, Any]]:
    """
    Retrieves the recent application logs for the specified service.
    """
    now = datetime.utcnow()
    logs = []
    
    # Generate logs corresponding to the active simulator state
    # Log format: time | level | message
    base_messages = [
        ("INFO", "api_gateway: Incoming prediction request"),
        ("INFO", f"model_runner: Running inference using checkpoint {sim_state.model_version}"),
        ("INFO", "api_gateway: Request completed successfully"),
    ]
    
    error_messages = [
        ("ERROR", "preprocessing: Failed to scale features. Scaling outputs contain NaN or infinity!"),
        ("WARNING", "preprocessing: Standard Scaler features calculated. Mean shifted to 0, values outside [0,1]. Model output might degrade."),
        ("ERROR", "model_runner: Model inference failed with standard scale inputs. Out-of-bounds features mapped to uncalibrated nodes.")
    ]

    drift_messages = [
        ("WARNING", "data_monitor: Input feature drift detected. Mass size mean exceeds historical thresholds (+2.4 stddev)."),
        ("INFO", "model_runner: Low confidence score on image sample.")
    ]

    dependency_messages = [
        ("ERROR", "numpy_loader: Found deprecation warning on float type rounding. Truncating values."),
        ("WARNING", "model_runner: Silent float rounding mismatch in linear weights layer. Output probabilities saturated.")
    ]
    
    resource_messages = [
        ("WARNING", "api_gateway: Queued request latency exceeds thread pool timeout threshold (1500ms)."),
        ("ERROR", "api_gateway: Timeout waiting for model thread lock acquisition.")
    ]

    # Generate log history
    for i in range(limit):
        log_time = now - timedelta(seconds=(limit - i) * 15)
        # Select message set
        level, msg = base_messages[i % len(base_messages)]
        
        # Inject fault-specific logs if post-deployment (18m ago) and active
        is_post_deploy = log_time >= (now - timedelta(minutes=18))
        if is_post_deploy:
            if "preprocessing_mismatch" in sim_state.active_faults and i % 3 == 0:
                level, msg = random_choice_static(error_messages)
            elif "data_drift" in sim_state.active_faults and i % 4 == 0:
                level, msg = random_choice_static(drift_messages)
            elif "dependency_regression" in sim_state.active_faults and i % 3 == 0:
                level, msg = random_choice_static(dependency_messages)
            elif "resource_limit" in sim_state.active_faults and i % 2 == 0:
                level, msg = random_choice_static(resource_messages)

        logs.append({
            "timestamp": log_time.isoformat(),
            "level": level,
            "message": f"[{service}] {msg}"
        })
        
    return logs

def random_choice_static(lst):
    # Static random selection based on time to remain deterministic per request
    t = int(time_seconds_hash() * 1000)
    return lst[t % len(lst)]

def time_seconds_hash():
    import time
    return time.time()

def get_git_commits() -> List[Dict[str, Any]]:
    """
    Retrieves git commit history.
    """
    return GIT_HISTORY

def get_git_diff(commit_a: str, commit_b: str) -> str:
    """
    Returns the git diff between two commit hashes.
    """
    for commit in GIT_HISTORY:
        if commit["commit"] == commit_a:
            return commit.get("diff", "No diff available")
    return "Commit hash not found"

def get_deployment_history(service: str) -> List[Dict[str, Any]]:
    """
    Retrieves recent deployment actions.
    """
    return [d for d in DEPLOYMENT_HISTORY if d["service"] == service]

def get_traces(service: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Retrieves distributed traces for the given service.
    Simulates span-level breakdown of an inference request.
    """
    from backend.app.simulator import sim_state
    traces = []
    now = datetime.utcnow()

    latency_base = 0.18
    if sim_state.latency_injection > 0:
        latency_base = sim_state.latency_injection

    for i in range(limit):
        trace_time = now - timedelta(seconds=(limit - i) * 30)
        preprocess_ms = random.uniform(5, 15) if sim_state.preprocessing_mode == "minmax" else random.uniform(80, 300)
        inference_ms = random.uniform(80, 150)
        postprocess_ms = random.uniform(1, 5)
        queue_ms = random.uniform(0, 5)
        if "resource_limit" in sim_state.active_faults:
            queue_ms = random.uniform(400, 1500)

        traces.append({
            "trace_id": f"trace-{i:04d}",
            "timestamp": trace_time.isoformat(),
            "service": service,
            "total_latency_ms": round(preprocess_ms + inference_ms + postprocess_ms + queue_ms, 2),
            "spans": [
                {"name": "queue_wait", "duration_ms": round(queue_ms, 2)},
                {"name": "preprocess", "duration_ms": round(preprocess_ms, 2)},
                {"name": "model_inference", "duration_ms": round(inference_ms, 2)},
                {"name": "postprocess", "duration_ms": round(postprocess_ms, 2)},
            ],
            "status": "OK" if queue_ms < 1200 else "TIMEOUT",
        })

    return traces


def inspect_dataset() -> Dict[str, Any]:
    """
    Returns metadata and statistics about the current production dataset.
    Reflects any active data drift injection.
    """
    from backend.app.simulator import EVAL_DATASET, sim_state

    all_features = [s["features"] for s in EVAL_DATASET]
    n_features = len(all_features[0]) if all_features else 0
    n_samples = len(EVAL_DATASET)

    feature_means = []
    for f in range(n_features):
        vals = [row[f] for row in all_features]
        feature_means.append(round(sum(vals) / len(vals), 4))

    drift_applied = sim_state.drift_multiplier > 1.0
    description = (
        f"{n_samples} mammography cases, {n_features} features (age, density, size, margin, shape). "
        f"Drift active: {drift_applied} (multiplier={sim_state.drift_multiplier})."
    )

    return {
        "n_samples": n_samples,
        "n_features": n_features,
        "feature_names": ["age", "density", "size", "margin", "shape"],
        "feature_means": feature_means,
        "drift_multiplier": sim_state.drift_multiplier,
        "description": description,
    }


def inspect_model() -> Dict[str, Any]:
    """
    Returns metadata about the currently loaded model version.
    Reflects any active model mismatch fault.
    """
    from backend.app.simulator import sim_state
    import hashlib

    version = sim_state.model_version
    if version == "v1.2.0":
        weights = [0.15, 0.2, 0.35, 0.15, 0.15]
        bias = -0.25
        description = "Calibrated production model (MinMax normalization compatible)."
    else:
        weights = [0.1, 0.1, 0.2, 0.1, 0.1]
        bias = 0.1
        description = "UN-calibrated model — StandardScaler weights, mismatched with current preprocessing."

    weight_str = ",".join(str(w) for w in weights) + f",b={bias}"
    model_hash = hashlib.sha256(weight_str.encode()).hexdigest()[:12]

    return {
        "version": version,
        "hash": model_hash,
        "weights": weights,
        "bias": bias,
        "normalization_compatible": "minmax" if version == "v1.2.0" else "standard_scaler",
        "description": description,
    }


def run_sandbox_script(script_content: str) -> Dict[str, Any]:
    """
    Executes a custom Python diagnostic script inside the sandbox.
    Sandbox workspace contains dataset.py, preprocessing.py, and model.py.
    """
    return sandbox_manager.execute_script(script_content)
