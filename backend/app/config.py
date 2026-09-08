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
    
    use_docker_sandbox: bool = True
    docker_image_name: str = "rootcause-sandbox:latest"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
