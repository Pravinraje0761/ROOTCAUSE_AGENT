import os
import sys
import tempfile
import subprocess
import shutil
import logging
from typing import Dict, Any, Tuple
from backend.app.config import settings

logger = logging.getLogger(__name__)

def prepare_sandbox_workspace(directory: str):
    from backend.app.simulator import sim_state
    import shutil
    
    # Paths to copy
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    src_backend = os.path.join(base_dir, "WE_WILL_WIN", "neoguard_app", "backend")
    src_static = os.path.join(base_dir, "WE_WILL_WIN", "neoguard_app", "static")
    
    # 1. Copy backend and static folders
    shutil.copytree(src_backend, directory, dirs_exist_ok=True)
    shutil.copytree(src_static, os.path.join(directory, "static"), dirs_exist_ok=True)
    
    # 2. Inject Preprocessing bug if active
    if sim_state.preprocessing_mode == "standard_scaler":
        norm_file = os.path.join(directory, "src", "real_data", "uncalibrated_normalization.py")
        if os.path.exists(norm_file):
            with open(norm_file, "r", encoding="utf-8") as f:
                code = f.read()
            # Replace gains scaling with Standard scaler math bug
            code_buggy = code.replace(
                "normalized = img * gains",
                "# Math bug injection: standard scaling instead of gains\n    normalized = (img - 128.0) / 74.0"
            )
            with open(norm_file, "w", encoding="utf-8") as f:
                f.write(code_buggy)

    # 3. Inject Model Mismatch bug if active
    if sim_state.model_version == "v2.0.0-uncalibrated":
        app_file = os.path.join(directory, "app.py")
        if os.path.exists(app_file):
            with open(app_file, "r", encoding="utf-8") as f:
                code = f.read()
            # Intercept classification probability calculation in endpoint
            code_buggy = code.replace(
                "prob_jaundice = float(clf.predict_proba(vec)[0, 1])",
                "# Model skew: uncalibrated model version loaded\n    prob_jaundice = 0.50"
            )
            with open(app_file, "w", encoding="utf-8") as f:
                f.write(code_buggy)

    # 4. Inject Data Drift bug if active
    if sim_state.drift_multiplier > 1.0:
        app_file = os.path.join(directory, "app.py")
        if os.path.exists(app_file):
            with open(app_file, "r", encoding="utf-8") as f:
                code = f.read()
            # Multiply color features by drift multiplier inside predictions
            code_buggy = code.replace(
                "vec = features_to_vector(features).reshape(1, -1)",
                f"vec = features_to_vector(features).reshape(1, -1)\n    # Feature drift injection\n    vec = vec * {sim_state.drift_multiplier}"
            )
            with open(app_file, "w", encoding="utf-8") as f:
                f.write(code_buggy)

    # 5. Inject Dependency Version bug if active (NumPy 2.0 truncation)
    if sim_state.dependency_version == "2.0.0":
        feat_file = os.path.join(directory, "src", "feature_extraction.py")
        if os.path.exists(feat_file):
            with open(feat_file, "r", encoding="utf-8") as f:
                code = f.read()
            # Append comment for diagnostic script to verify
            code += "\n# NumPy 2.0.0 float truncation simulation active\n"
            with open(feat_file, "w", encoding="utf-8") as f:
                f.write(code)

    # 6. Inject Resource Limit bug if active (Threading workers config)
    # Write worker limit config file or inject directly into app.py
    app_file = os.path.join(directory, "app.py")
    if os.path.exists(app_file):
        with open(app_file, "r", encoding="utf-8") as f:
            code = f.read()
        if sim_state.latency_injection > 0 and "resource_limit" in sim_state.active_faults:
            # Limit pool config
            code_buggy = code.replace(
                "app = FastAPI(title=\"NeoGuard API\")",
                "app = FastAPI(title=\"NeoGuard API\")\n# Worker Thread Pool limit: max_workers=1 active\n"
            )
            with open(app_file, "w", encoding="utf-8") as f:
                f.write(code_buggy)



class SandboxManager:
    def __init__(self):
        self.use_docker = settings.use_docker_sandbox
        self.image_name = settings.docker_image_name
        self.docker_client = None

        if self.use_docker:
            try:
                import docker
                self.docker_client = docker.from_env()
                # Ping docker to ensure it's running
                self.docker_client.ping()
                logger.info("Successfully connected to Docker Daemon.")
            except Exception as e:
                logger.warning(f"Failed to initialize Docker client ({e}). Falling back to Local Subprocess execution.")
                self.use_docker = False

    def execute_script(self, script_content: str, timeout_s: int = 15) -> Dict[str, Any]:
        """
        Executes a diagnostic script inside the sandbox and returns stdout, stderr, and exit code.
        """
        if self.use_docker:
            return self._execute_in_docker(script_content, timeout_s)
        else:
            return self._execute_locally(script_content, timeout_s)

    def _execute_in_docker(self, script_content: str, timeout_s: int) -> Dict[str, Any]:
        """
        Runs the python code inside a Docker container.
        """
        # Ensure we have the sandbox image. If not, build it.
        self._ensure_sandbox_image()

        with tempfile.TemporaryDirectory() as temp_dir:
            script_path = os.path.join(temp_dir, "diagnostic.py")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(script_content)
            prepare_sandbox_workspace(temp_dir)

            try:
                # Mount the temp directory and execute the script
                container = self.docker_client.containers.create(
                    image=self.image_name,
                    command=["python", "/workspace/diagnostic.py"],
                    volumes={
                        temp_dir: {"bind": "/workspace", "mode": "rw"}
                    },
                    network_mode="none",  # Security boundary: no internet access
                    mem_limit="128m",     # Limit memory
                    nano_cpus=1000000000  # Limit to 1 CPU core
                )
                
                container.start()
                
                # Wait for container execution
                result = container.wait(timeout=timeout_s)
                exit_code = result.get("StatusCode", -1)
                
                stdout = container.logs(stdout=True, stderr=False).decode("utf-8")
                stderr = container.logs(stdout=False, stderr=True).decode("utf-8")
                
                container.remove(force=True)

                return {
                    "exit_code": exit_code,
                    "stdout": stdout,
                    "stderr": stderr,
                    "sandbox_type": "docker"
                }
            except Exception as e:
                logger.error(f"Docker execution failed: {e}")
                # Try fallback
                return self._execute_locally(script_content, timeout_s)

    def _execute_locally(self, script_content: str, timeout_s: int) -> Dict[str, Any]:
        """
        Runs python script in a separate local process using subprocess.run
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            script_path = os.path.join(temp_dir, "diagnostic.py")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(script_content)
            prepare_sandbox_workspace(temp_dir)

            # Copy current sys.path to run locally, but clean env vars for security
            clean_env = {
                "PATH": os.environ.get("PATH", ""),
                "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),  # Needed for Windows
                "TEMP": temp_dir,
                "TMP": temp_dir
            }

            try:
                proc = subprocess.run(
                    [sys.executable, "diagnostic.py"],
                    cwd=temp_dir,
                    env=clean_env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=timeout_s,
                    text=True
                )
                return {
                    "exit_code": proc.returncode,
                    "stdout": proc.stdout,
                    "stderr": proc.stderr,
                    "sandbox_type": "local"
                }
            except subprocess.TimeoutExpired as e:
                return {
                    "exit_code": -1,
                    "stdout": e.stdout if isinstance(e.stdout, str) else "",
                    "stderr": "Execution Timeout Expired (Limit: 15s)",
                    "sandbox_type": "local"
                }
            except Exception as e:
                return {
                    "exit_code": -1,
                    "stdout": "",
                    "stderr": f"Local sandbox execution failed: {e}",
                    "sandbox_type": "local"
                }

    def _ensure_sandbox_image(self):
        """
        Ensures the Docker image exists, or builds a simple one.
        """
        try:
            self.docker_client.images.get(self.image_name)
        except Exception:
            logger.info(f"Image {self.image_name} not found. Building it now...")
            # Write a simple Dockerfile and build it
            with tempfile.TemporaryDirectory() as temp_dir:
                dockerfile_content = """FROM python:3.10-slim
WORKDIR /workspace
RUN pip install numpy pandas scikit-learn scipy
"""
                with open(os.path.join(temp_dir, "Dockerfile"), "w") as f:
                    f.write(dockerfile_content)
                
                self.docker_client.images.build(
                    path=temp_dir,
                    tag=self.image_name,
                    rm=True
                )
                logger.info(f"Successfully built {self.image_name}")

sandbox_manager = SandboxManager()
