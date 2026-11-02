import os
import logging
from pathlib import Path
from typing import Dict, Any, AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text

from app.config import BASE_DIR, settings

logger = logging.getLogger("pravision.storage.db")

Base = declarative_base()

# Resolve Database URL:
# 1. POSTGRES_URL environment variable or settings.postgres_url
# 2. Defaults to local SQLite with WAL mode in base directory
DEFAULT_SQLITE_PATH = BASE_DIR / "pravision_local.db"
POSTGRES_ENV = os.environ.get("POSTGRES_URL")

if POSTGRES_ENV:
    # Ensure async driver
    if POSTGRES_ENV.startswith("postgresql://"):
        DATABASE_URL = POSTGRES_ENV.replace("postgresql://", "postgresql+asyncpg://", 1)
    else:
        DATABASE_URL = POSTGRES_ENV
    IS_POSTGRES = True
else:
    DATABASE_URL = f"sqlite+aiosqlite:///{DEFAULT_SQLITE_PATH}"
    IS_POSTGRES = False

engine_kwargs = {}
if IS_POSTGRES:
    engine_kwargs.update({
        "pool_size": 10,
        "max_overflow": 20,
        "pool_pre_ping": True,
    })
else:
    engine_kwargs.update({
        "connect_args": {"check_same_thread": False}
    })

engine = create_async_engine(DATABASE_URL, echo=False, **engine_kwargs)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def init_db():
    """Initializes schema and tables."""
    from app.storage.models_db import CaseModel, InvestigationModel, EntityModel, RelationshipModel, EvidenceModel, AuditLogModel
    async with engine.begin() as conn:
        if not IS_POSTGRES:
            # Enable WAL mode for high performance SQLite concurrency
            await conn.execute(text("PRAGMA journal_mode=WAL;"))
            await conn.execute(text("PRAGMA foreign_keys=ON;"))
        await conn.run_sync(Base.metadata.create_all)
    logger.info(f"Database initialized successfully on {'PostgreSQL' if IS_POSTGRES else 'Local SQLite (WAL)'}")

async def check_db_health() -> Dict[str, Any]:
    """Health check endpoint for DB engine."""
    import time
    start = time.time()
    try:
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1;"))
        latency_ms = round((time.time() - start) * 1000, 2)
        return {
            "status": "healthy",
            "backend": "PostgreSQL" if IS_POSTGRES else "SQLite (WAL)",
            "database_url_masked": DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL,
            "latency_ms": latency_ms,
            "is_postgres": IS_POSTGRES
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "backend": "PostgreSQL" if IS_POSTGRES else "SQLite",
            "error": str(e),
            "is_postgres": IS_POSTGRES
        }

