import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent.parent
WORKSPACE_DIR = BASE_DIR.parent
# Load .env from project root
load_dotenv(WORKSPACE_DIR / ".env")
load_dotenv(WORKSPACE_DIR / ".env.local")
TEMP_DATA_DIR = BASE_DIR / "temp_runtime"
VAULT_DATA_DIR = BASE_DIR / "evidence_vault"

class InvestigationLimits(BaseModel):
    max_depth: int = Field(default=2, ge=1, le=5)
    max_discovered_entities: int = Field(default=150, ge=10, le=1000)
    max_concurrent_connectors: int = Field(default=8, ge=1, le=20)
    connector_timeout_seconds: int = Field(default=35, ge=5, le=180)
    max_requests_per_provider: int = Field(default=10, ge=1, le=50)
    max_file_size_mb: int = Field(default=25, ge=1, le=100)
    enable_recursive_expansion: bool = Field(default=True)

def get_configured_cors_origins() -> list[str]:
    is_prod = os.environ.get("ENVIRONMENT", "").lower() == "production" or os.environ.get("PRAVISION_ENV", "").lower() == "production"
    prod_origins = ["https://pravision.pages.dev"]
    env_origins = [orig.strip() for orig in os.environ.get("CORS_ORIGINS", "").split(",") if orig.strip()]
    if is_prod:
        return list(dict.fromkeys(prod_origins + env_origins))
    dev_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]
    return list(dict.fromkeys(prod_origins + dev_origins + env_origins))

class PravisionSettings(BaseModel):
    app_name: str = "PRAVISION"
    full_name: str = "PRAVISION — Universal OSINT & Intelligence Platform"
    tagline: str = "See Everything. Connect Everything. Understand Everything."
    version: str = "1.0.0"
    
    # Server network binding
    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: list[str] = Field(default_factory=get_configured_cors_origins)
    
    # Critical Privacy Directive: Absolutely NO persistent target history
    persist_investigations: bool = False
    ephemeral_data_dir: Path = TEMP_DATA_DIR
    
    # Investigation limits
    limits: InvestigationLimits = InvestigationLimits()
    
    # Tool execution paths
    ghunt_executable: str = r"C:\Users\hp\.local\bin\ghunt.exe"
    python_executable: str = str(WORKSPACE_DIR / "venv" / "Scripts" / "python.exe")

settings = PravisionSettings()

# Ensure directories exist
TEMP_DATA_DIR.mkdir(parents=True, exist_ok=True)
VAULT_DATA_DIR.mkdir(parents=True, exist_ok=True)

