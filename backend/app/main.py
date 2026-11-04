import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

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

class MandatoryAuthMiddleware(BaseHTTPMiddleware):
    """
    Guarantees that all protected backend API routes require a valid authenticated session.
    Public access is strictly restricted to login, session check, and minimal health status.
    """
    PUBLIC_PREFIXES = (
        "/api/auth/login",
        "/api/auth/session",
        "/api/storage/status",
        "/temp-media",
        "/assets",
    )
    PUBLIC_EXACT = (
        "/api/auth/login",
        "/api/auth/session",
        "/api/storage/status",
        "/favicon.ico",
        "/",
        "/index.html",
    )

    async def dispatch(self, request: Request, call_next):
        # 1. CORS Preflight is handled by CORSMiddleware
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path

        # 2. Allow non-API static files and SPA root
        if not path.startswith("/api/"):
            return await call_next(request)

        # 3. Allow explicitly public API endpoints
        if path in self.PUBLIC_EXACT or any(path.startswith(prefix) for prefix in self.PUBLIC_PREFIXES):
            return await call_next(request)

        # 4. Enforce authentication on all other /api/* routes
        token = None
        auth_head = request.headers.get("Authorization") or request.headers.get("authorization")
        if auth_head and auth_head.startswith("Bearer "):
            token = auth_head[7:].strip()
        elif "pravision_session" in request.cookies:
            token = request.cookies.get("pravision_session")
        elif "pravision_token" in request.cookies:
            token = request.cookies.get("pravision_token")

        if not token:
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required. Please log in to access PRAVISION."},
                headers={"WWW-Authenticate": "Bearer"}
            )

        try:
            from app.auth.auth_service import decode_jwt_token, auth_service
            payload = decode_jwt_token(token)
            jti = payload.get("jti")
            if jti and await auth_service.is_token_revoked(jti):
                return JSONResponse(status_code=401, content={"detail": "Session has been invalidated. Please log in again."})
        except Exception as e:
            return JSONResponse(status_code=401, content={"detail": f"Invalid or expired session credentials: {str(e)}"})

        return await call_next(request)

# Enforce mandatory authentication across all API endpoints
app.add_middleware(MandatoryAuthMiddleware)

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
