import random
import time
import math
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel

# --- SIMULATOR CONFIG & STATE ---
class SimulatorState:
    def __init__(self):
        self.reset()

    def reset(self):
        self.model_version = "v1.2.0"
        self.preprocessing_mode = "minmax"  # "minmax" (healthy), "standard_scaler" (broken)
        self.drift_multiplier = 1.0        # 1.0 (healthy), 1.8 (drifted)
        self.dependency_version = "1.24.2"  # "1.24.2" (healthy), "2.0.0" (broken)
        self.latency_injection = 0.0       # Added latency in seconds
        self.concurrency_limit = 8         # Thread workers limit
        self.active_faults = []
        self.request_history = []
        self.start_time = datetime.utcnow() - timedelta(hours=2)

sim_state = SimulatorState()

# --- EVALUATION DATASET (100 SAMPLE CASE METADATA) ---
# Age, Density, Size, Margin, Shape, Calcification, Distribution, Prior (all scaled 0-1)
# Label: 0 = Benign, 1 = Malignant
EVAL_DATASET = []
random.seed(42)
for i in range(100):
    age = random.uniform(0.2, 0.9)
    density = random.uniform(0.1, 0.8)
    size = random.uniform(0.1, 0.9)
    margin = random.uniform(0.0, 1.0)
    shape = random.uniform(0.0, 1.0)
    
    # Ground truth determination:
    score = age * 0.15 + density * 0.2 + size * 0.35 + margin * 0.15 + shape * 0.15
    label = 1 if score > 0.5 else 0
    
    EVAL_DATASET.append({
        "id": i,
        "features": [age, density, size, margin, shape],
        "label": label
    })

# --- GIT COMMIT HISTORY ---
GIT_HISTORY = [
    {
        "commit": "8f31a2c",
        "author": "dev-alice@rootcause.ai",
        "date": (datetime.utcnow() - timedelta(minutes=18)).isoformat(),
        "message": "Optimize feature normalization scale for edge case mammographies",
        "diff": """diff --git a/preprocessing.py b/preprocessing.py
index a210dfc..9f81a3d 100644
--- a/preprocessing.py
+++ b/preprocessing.py
@@ -10,5 +10,5 @@ def normalize_features(features):
-    # MinMax scaling: (x - min) / (max - min)
-    return [(x - 0.0) / (1.0 - 0.0) for x in features]
+    # Standard scaling: (x - mean) / std for zero mean unit variance
+    return [(x - 0.5) / 0.288 for x in features]
"""
    },
    {
        "commit": "3b77e11",
        "author": "dev-bob@rootcause.ai",
        "date": (datetime.utcnow() - timedelta(hours=1, minutes=30)).isoformat(),
        "message": "Update inference runner thread count config",
        "diff": """diff --git a/config.yaml b/config.yaml
index e11a8c9..f2b3c41 100644
--- a/config.yaml
+++ b/config.yaml
@@ -5,2 +5,2 @@ inference:
-  max_workers: 8
+  max_workers: 1
"""
    },
    {
        "commit": "f471e98",
        "author": "dev-alice@rootcause.ai",
        "date": (datetime.utcnow() - timedelta(days=1)).isoformat(),
        "message": "Merge branch 'main' into production-stable",
        "diff": "Merge branch 'main'"
    }
]

# --- DEPLOYMENT HISTORY ---
DEPLOYMENT_HISTORY = [
    {
        "id": "DEP-401",
        "service": "image-classification-api",
        "version": "v1.2.1",
        "commit": "8f31a2c",
        "timestamp": (datetime.utcnow() - timedelta(minutes=18)).isoformat(),
        "status": "SUCCESS"
    },
    {
        "id": "DEP-400",
        "service": "image-classification-api",
        "version": "v1.2.0",
        "commit": "f471e98",
        "timestamp": (datetime.utcnow() - timedelta(days=1)).isoformat(),
        "status": "SUCCESS"
    }
]

# --- PREDICTION LOGIC & TELEMETRY GENERATOR ---
def run_model_inference(features: List[float]) -> Dict[str, Any]:
    """
    Runs model inference with simulated preprocessing, model version, and dependency version.
    Returns: Dict containing prediction, raw outputs, and execution telemetry
    """
    steps_telemetry = []
    
    # 1. Read Inputs
    t0 = time.time()
    steps_telemetry.append({"step": "read_inputs", "duration_ms": random.uniform(2, 5)})
    
    # 2. Preprocessing
    t1 = time.time()
    processed_features = []
    
    # Simulating standard scaling vs minmax preprocessing fault
    if sim_state.preprocessing_mode == "minmax":
        # Healthy MinMax
        processed_features = [max(0.0, min(1.0, x)) for x in features]
    elif sim_state.preprocessing_mode == "standard_scaler":
        # Fault: Standard Scaler applied without updating model weights
        # Shifts inputs: (x - 0.5) / 0.288
        processed_features = [(x - 0.5) / 0.288 for x in features]
        # Introduce resource contention latency simulation for H3/Resource fault if latency injection is enabled
        if sim_state.latency_injection > 0:
            time.sleep(sim_state.latency_injection / 3.0)

    # Simulating data drift fault
    if sim_state.drift_multiplier > 1.0:
        processed_features = [x * sim_state.drift_multiplier for x in processed_features]

    steps_telemetry.append({"step": "preprocess", "duration_ms": (time.time() - t1) * 1000})

    # 3. Model Version weights
    t2 = time.time()
    # v1.2.0 is the calibrated model
    if sim_state.model_version == "v1.2.0":
        weights = [0.15, 0.2, 0.35, 0.15, 0.15]
        bias = -0.25
    else:  # e.g., "v2.0.0-uncalibrated"
        weights = [0.1, 0.1, 0.2, 0.1, 0.1]
        bias = 0.1

    # Dependency issue (NumPy 2.0.0 roundoff simulation)
    if sim_state.dependency_version == "2.0.0":
        # Simulates truncation error
        processed_features = [round(x, 1) for x in processed_features]

    # Calculate model score
    score = sum(w * x for w, x in zip(weights, processed_features)) + bias
    # Sigmoid function for probability
    probability = 1.0 / (1.0 + math.exp(-score))
    
    # Simulating dependency bug where output becomes binary thresholded early
    if sim_state.dependency_version == "2.0.0" and random.random() < 0.2:
        probability = 1.0 if probability > 0.5 else 0.0

    prediction = 1 if probability > 0.5 else 0
    
    if sim_state.latency_injection > 0:
        time.sleep(sim_state.latency_injection * 0.6)

    steps_telemetry.append({"step": "model_inference", "duration_ms": (time.time() - t2) * 1000})
    
    # Postprocessing
    t3 = time.time()
    steps_telemetry.append({"step": "postprocess", "duration_ms": random.uniform(1, 3)})

    total_duration = (time.time() - t0)
    
    return {
        "prediction": prediction,
        "probability": probability,
        "features_used": processed_features,
        "latency_s": total_duration,
        "steps": steps_telemetry
    }

def generate_telemetry_history(seconds_ago: int = 7200, interval_s: int = 60) -> List[Dict[str, Any]]:
    """
    Generates historical metrics, logs, and traces.
    Correctly models the transition at the deployment time (18 minutes ago).
    """
    now = datetime.utcnow()
    history = []
    
    # 18 minutes ago deployment
    deployment_time = now - timedelta(minutes=18)
    
    current_time = now - timedelta(seconds=seconds_ago)
    
    while current_time < now:
        # Check simulator state configuration relative to deployment time
        is_post_deployment = current_time >= deployment_time
        
        # Determine error/latency metrics based on simulation state
        if is_post_deployment:
            # We are in the failed state (reflect current active state)
            mode = sim_state.preprocessing_mode
            version = sim_state.model_version
            drift = sim_state.drift_multiplier
            dep = sim_state.dependency_version
            lat_inj = sim_state.latency_injection
        else:
            # Pre-deployment: healthy defaults
            mode = "minmax"
            version = "v1.2.0"
            drift = 1.0
            dep = "1.24.2"
            lat_inj = 0.0

        # Run 20 simulated requests for this interval
        interval_latency = []
        correct_predictions = 0
        total_requests = 20
        error_count = 0

        for i in range(total_requests):
            sample = random.choice(EVAL_DATASET)
            
            # Apply preprocessing
            features = sample["features"]
            # Apply drift multiplier to inputs if post-deployment and drift is active
            if is_post_deployment and drift > 1.0:
                features = [x * drift for x in features]
                
            # Perform inference
            processed_features = features
            if mode == "minmax":
                processed_features = [max(0.0, min(1.0, x)) for x in features]
            elif mode == "standard_scaler":
                processed_features = [(x - 0.5) / 0.288 for x in features]

            # Model parameters
            if version == "v1.2.0":
                weights = [0.15, 0.2, 0.35, 0.15, 0.15]
                bias = -0.25
            else:
                weights = [0.1, 0.1, 0.2, 0.1, 0.1]
                bias = 0.1

            if dep == "2.0.0":
                processed_features = [round(x, 1) for x in processed_features]

            score = sum(w * x for w, x in zip(weights, processed_features)) + bias
            probability = 1.0 / (1.0 + math.exp(-score))
            pred = 1 if probability > 0.5 else 0

            # Calculate accuracy
            if pred == sample["label"]:
                correct_predictions += 1
            
            # Error simulation (e.g. standard scaler scaling causing NaNs or out of range math errors)
            if mode == "standard_scaler" and any(math.isnan(x) or abs(x) > 10 for x in processed_features):
                error_count += 1
            # Standard error rate model:
            elif mode == "standard_scaler" and random.random() < 0.15:
                error_count += 1
            elif dep == "2.0.0" and random.random() < 0.08:
                error_count += 1
            else:
                if random.random() < 0.004:  # baseline error rate
                    error_count += 1

            # Latency simulation
            base_latency = 0.18  # 180 ms
            if lat_inj > 0:
                base_latency = lat_inj
            
            # Add small random noise
            request_latency = base_latency + random.uniform(-0.02, 0.02)
            interval_latency.append(request_latency)

        avg_latency = sum(interval_latency) / len(interval_latency)
        accuracy = correct_predictions / total_requests
        error_rate = error_count / total_requests

        history.append({
            "timestamp": current_time.isoformat(),
            "accuracy": accuracy,
            "latency": avg_latency,
            "error_rate": error_rate,
            "requests": total_requests
        })

        current_time += timedelta(seconds=interval_s)

    return history

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/simulator", tags=["simulator"])

@router.get("/metrics")
def get_simulator_metrics(seconds_ago: int = 7200, interval_s: int = 60):
    return generate_telemetry_history(seconds_ago, interval_s)

@router.get("/git/commits")
def get_git_commits():
    return GIT_HISTORY

@router.get("/deployments")
def get_deployments():
    return DEPLOYMENT_HISTORY

@router.post("/inject")
def inject_fault(fault_type: str):
    sim_state.reset()
    if fault_type == "preprocessing_mismatch":
        sim_state.preprocessing_mode = "standard_scaler"
        sim_state.latency_injection = 2.2
        sim_state.active_faults = ["preprocessing_mismatch"]
    elif fault_type == "wrong_model":
        sim_state.model_version = "v2.0.0-uncalibrated"
        sim_state.active_faults = ["wrong_model"]
    elif fault_type == "data_drift":
        sim_state.drift_multiplier = 1.8
        sim_state.active_faults = ["data_drift"]
    elif fault_type == "dependency_regression":
        sim_state.dependency_version = "2.0.0"
        sim_state.active_faults = ["dependency_regression"]
    elif fault_type == "resource_limit":
        sim_state.latency_injection = 2.4
        sim_state.active_faults = ["resource_limit"]
    else:
        raise HTTPException(status_code=400, detail="Invalid fault type")
    return {"status": "success", "active_faults": sim_state.active_faults}

@router.post("/reset")
def reset_simulator():
    sim_state.reset()
    return {"status": "success", "active_faults": sim_state.active_faults}

class PredictionRequest(BaseModel):
    features: List[float]

@router.post("/predict")
def predict(request: PredictionRequest):
    try:
        res = run_model_inference(request.features)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

