import os
from pydantic_settings import BaseSettings
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    port: int = 8000
    host: str = "0.0.0.0"
    database_url: str = "postgresql://postgres:postgres@localhost:5432/rootcause_db"
    
    openai_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    nvidia_api_key: Optional[str] = None
    
    # The application the agent investigates (its sandbox copies and patches this).
    # Defaults to WE_WILL_WIN/neoguard_app at the repository root; CI checks out the
    # public NeoGuard repository there. Override with TARGET_APP_DIR.
    target_app_dir: str = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "WE_WILL_WIN", "neoguard_app")

    use_docker_sandbox: bool = True
    docker_image_name: str = "rootcause-sandbox:latest"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
