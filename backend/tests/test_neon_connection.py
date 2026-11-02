import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

async def test_neon_postgres():
    raw_url = os.environ.get("DATABASE_URL")
    print(f"DATABASE_URL present: {bool(raw_url)}")
    if not raw_url:
        print("DATABASE_URL is not set!")
        return

    import urllib.parse
    parsed = urllib.parse.urlparse(raw_url)
    qs = urllib.parse.parse_qs(parsed.query)
    # Remove asyncpg-unsupported query params like channel_binding and map sslmode to ssl
    qs.pop("channel_binding", None)
    if "sslmode" in qs:
        ssl_val = qs.pop("sslmode")[0]
        qs["ssl"] = [ssl_val]
    new_query = urllib.parse.urlencode(qs, doseq=True)
    clean_url = urllib.parse.urlunparse(parsed._replace(scheme="postgresql+asyncpg", query=new_query))

    print("Testing asyncpg engine connection to Neon with cleaned URL...")
    engine = create_async_engine(clean_url, pool_pre_ping=True)
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT version(), current_database(), current_user;"))
        row = res.fetchone()
        print(f"Successfully connected to Neon Lakebase Postgres!")
        print(f"  Postgres Version: {row[0]}")
        print(f"  Database: {row[1]}")
        print(f"  User: {row[2]}")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test_neon_postgres())
