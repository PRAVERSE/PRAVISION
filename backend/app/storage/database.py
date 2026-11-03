import os
import asyncio
import logging
import urllib.parse
from pathlib import Path
from typing import Dict, Any, AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text

from app.config import BASE_DIR, settings

logger = logging.getLogger("pravision.storage.db")

Base = declarative_base()

# Resolve Database URL:
# 1. Neon Postgres: DATABASE_URL or DATABASE_URL_UNPOOLED (from neon deploy)
# 2. POSTGRES_URL environment variable
# 3. Defaults to local SQLite with WAL mode in base directory
DEFAULT_SQLITE_PATH = BASE_DIR / "pravision_local.db"
RAW_DB_URL = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL") or os.environ.get("DATABASE_URL_UNPOOLED")
NEON_BRANCH = os.environ.get("NEON_BRANCH")

if RAW_DB_URL and ("postgres" in RAW_DB_URL or "postgresql" in RAW_DB_URL):
    parsed = urllib.parse.urlparse(RAW_DB_URL)
    qs = urllib.parse.parse_qs(parsed.query)
    # Remove query parameters unsupported by asyncpg
    qs.pop("channel_binding", None)
    if "sslmode" in qs:
        ssl_val = qs.pop("sslmode")[0]
        qs["ssl"] = [ssl_val]
    elif "neon.tech" in (parsed.hostname or "") or not qs.get("ssl"):
        qs["ssl"] = ["require"]
    new_query = urllib.parse.urlencode(qs, doseq=True)
    DATABASE_URL = urllib.parse.urlunparse(parsed._replace(scheme="postgresql+asyncpg", query=new_query))
    IS_POSTGRES = True
    IS_NEON = "neon.tech" in (parsed.hostname or "")
else:
    DATABASE_URL = f"sqlite+aiosqlite:///{DEFAULT_SQLITE_PATH}"
    IS_POSTGRES = False
    IS_NEON = False

engine_kwargs = {}
if IS_POSTGRES:
    engine_kwargs.update({
        "pool_size": 15,
        "max_overflow": 25,
        "pool_timeout": 30,
        "pool_recycle": 300,
        "pool_pre_ping": True,
        "connect_args": {
            "command_timeout": 30,
            "server_settings": {"application_name": "pravision_backend"}
        }
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
    """Initializes schema, migrations, and tables with resilient retry."""
    from app.storage.models_db import (
        UserModel, CaseMembershipModel, RevokedTokenModel,
        CaseModel, InvestigationModel, EntityModel, RelationshipModel, EvidenceModel, AuditLogModel
    )
    for attempt in range(1, 4):
        try:
            async with engine.begin() as conn:
                if not IS_POSTGRES:
                    # Enable WAL mode for high performance SQLite concurrency
                    await conn.execute(text("PRAGMA journal_mode=WAL;"))
                    await conn.execute(text("PRAGMA foreign_keys=ON;"))
                await conn.run_sync(Base.metadata.create_all)

                # Idempotent column migrations for existing instances
                if IS_POSTGRES:
                    try:
                        await conn.execute(text("ALTER TABLE cases ADD COLUMN IF NOT EXISTS owner_id VARCHAR(36);"))
                        await conn.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS actor_id VARCHAR(36);"))
                        await conn.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS outcome VARCHAR(32) DEFAULT 'success';"))
                    except Exception as e:
                        logger.warning(f"Migration notice: {e}")
                else:
                    for query in [
                        "ALTER TABLE cases ADD COLUMN owner_id VARCHAR(36);",
                        "ALTER TABLE audit_logs ADD COLUMN actor_id VARCHAR(36);",
                        "ALTER TABLE audit_logs ADD COLUMN outcome VARCHAR(32) DEFAULT 'success';"
                    ]:
                        try:
                            await conn.execute(text(query))
                        except Exception:
                            pass
            backend_name = "Neon Lakebase Postgres" if IS_NEON else ("PostgreSQL" if IS_POSTGRES else "Local SQLite (WAL)")
            logger.info(f"Database initialized successfully on {backend_name}")
            return
        except Exception as e:
            if attempt == 3:
                raise
            logger.warning(f"Database initialization attempt {attempt} failed ({e}), retrying in 1s...")
            await asyncio.sleep(1.0)

async def check_db_health() -> Dict[str, Any]:
    """Health check endpoint for DB engine."""
    import time
    start = time.time()
    try:
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1;"))
        latency_ms = round((time.time() - start) * 1000, 2)
        backend_name = "Neon Lakebase Postgres" if IS_NEON else ("PostgreSQL" if IS_POSTGRES else "SQLite (WAL)")
        return {
            "status": "healthy",
            "backend": backend_name,
            "database_url_masked": DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL,
            "latency_ms": latency_ms,
            "is_postgres": IS_POSTGRES,
            "is_neon": IS_NEON,
            "neon_branch": NEON_BRANCH
        }
    except Exception as e:
        backend_name = "Neon Lakebase Postgres" if IS_NEON else ("PostgreSQL" if IS_POSTGRES else "SQLite")
        return {
            "status": "unhealthy",
            "backend": backend_name,
            "error": str(e),
            "is_postgres": IS_POSTGRES,
            "is_neon": IS_NEON,
            "neon_branch": NEON_BRANCH
        }

