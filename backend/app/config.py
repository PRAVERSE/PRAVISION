import os
from pathlib import Path
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent.parent
WORKSPACE_DIR = BASE_DIR.parent
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

class PravisionSettings(BaseModel):
    app_name: str = "PRAVISION"
    full_name: str = "PRAVISION — Universal OSINT & Intelligence Platform"
    tagline: str = "See Everything. Connect Everything. Understand Everything."
    version: str = "1.0.0"
    
    # Server network binding
    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]
    
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

