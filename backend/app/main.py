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

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("pravision.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing PRAVISION Intelligence Platform...")
    privacy_controller.purge_all_ephemeral_data()
    from app.storage.database import init_db
    from app.storage.backup_system import backup_scheduler
    try:
        await init_db()
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
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

# CORS configuration
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
