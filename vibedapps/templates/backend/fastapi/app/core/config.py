from pydantic_settings import BaseSettings
from typing import List, Optional
import os

class Settings(BaseSettings):
    # Project settings
    PROJECT_NAME: str = "DApp API"
    PROJECT_DESCRIPTION: str = "API for DApp Backend"
    PROJECT_VERSION: str = "0.1.0"
    
    # FastAPI settings
    DEBUG: bool = os.getenv("DEBUG", "False").lower() in ["true", "1", "t"]
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    
    # CORS
    CORS_ORIGINS: List[str] = ["*"]
    
    # Blockchain settings
    RPC_URL: str = os.getenv("RPC_URL", "")
    CONTRACT_ADDRESS: str = os.getenv("CONTRACT_ADDRESS", "")
    PRIVATE_KEY: Optional[str] = os.getenv("PRIVATE_KEY", None)
    
    class Config:
        env_file = ".env"

settings = Settings()
