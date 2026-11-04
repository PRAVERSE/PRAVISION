import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings, WORKSPACE_DIR
from app.api.router import router as api_router
from app.connectors.registry import connector_registry
from app.privacy.privacy_controller import privacy_controller

import re

class SensitiveParamRedactingFilter(logging.Filter):
    """
    Redacts sensitive authentication parameters (token, ticket, password, secret, key)
    from all log records before emission to disk or console.
    """
    REDACT_REGEX = re.compile(r'(token|ticket|password|secret|key|access_token)=([^&\s"\']+)', re.IGNORECASE)

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self.REDACT_REGEX.sub(r'\1=[REDACTED]', record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: (self.REDACT_REGEX.sub(r'\1=[REDACTED]', v) if isinstance(v, str) else v)
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, (list, tuple)):
                record.args = tuple(
                    (self.REDACT_REGEX.sub(r'\1=[REDACTED]', a) if isinstance(a, str) else a)
                    for a in record.args
                )
        return True

redaction_filter = SensitiveParamRedactingFilter()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logging.getLogger().addFilter(redaction_filter)
logging.getLogger("uvicorn.access").addFilter(redaction_filter)
logger = logging.getLogger("pravision.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing PRAVISION Intelligence Platform...")
    privacy_controller.purge_all_ephemeral_data()
    from app.storage.database import init_db
    from app.storage.backup_system import backup_scheduler
    from app.auth.auth_service import auth_service
    try:
        await init_db()
        await auth_service.seed_default_users()
    except Exception as e:
        logger.error(f"Failed to initialize database or security accounts: {e}")
    asyncio.create_task(connector_registry.run_all_health_checks())
    asyncio.create_task(backup_scheduler.start())
    yield
    logger.info("Shutting down PRAVISION. Purging ephemeral investigation buffers...")
    await backup_scheduler.stop()
    privacy_controller.purge_all_ephemeral_data()

app = FastAPI(
    title=settings.full_name,
    description="Universal OSINT & Intelligence Platform — Windows Local Intelligence Engine",
    version=settings.version,
    lifespan=lifespan
)

# CORS configuration (Strict allowlist: exact production origin + explicit env origins only)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ephemeral media upload directory
app.mount("/temp-media", StaticFiles(directory=str(settings.ephemeral_data_dir)), name="temp_media")

# API Router
app.include_router(api_router, prefix="/api")

# Serve built frontend if dist exists
dist_dir = WORKSPACE_DIR / "frontend" / "dist"
if dist_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(dist_dir / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = dist_dir / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(dist_dir / "index.html")
else:
    @app.get("/")
    async def root():
        return {
            "platform": settings.full_name,
            "tagline": settings.tagline,
            "version": settings.version,
            "status": "operational",
            "zero_history_mode": not settings.persist_investigations
        }
