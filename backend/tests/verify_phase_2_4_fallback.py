import asyncio
import os
import sys
import time
from pathlib import Path

# Add backend to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.storage.database import check_db_health, init_db
from app.storage.b2_storage import b2_storage
from app.storage.backup_system import backup_system

async def test_fallback_suite():
    print("=" * 80)
    print("PRAVISION PHASE 2.4 — FALLBACK & DISCONNECTED RESILIENCE AUDIT")
    print("=" * 80)
    start_time = time.time()

    await init_db()

    # 1. Health Status Reporting
    print("\n" + "-" * 70)
    print("CHECK 1: Storage Status & Health Reporting")
    print("-" * 70)
    db_health = await check_db_health()
    b2_status = b2_storage.get_status()
    print("DB Health:", db_health)
    print("Storage Status:", b2_status)
    assert db_health["status"] in ("healthy", "degraded")
    assert "backend" in db_health
    assert "provider" in b2_status
    print("[PASS] Storage status correctly attributes active backend engine.")

    # 2. Local Backup Directory & Manifest Verification
    print("\n" + "-" * 70)
    print("CHECK 2: Local Backup Staging Directory Integrity")
    print("-" * 70)
    from app.storage.backup_system import BACKUP_DIR, MANIFEST_FILE
    assert BACKUP_DIR.exists()
    assert BACKUP_DIR.is_dir()
    print(f"[PASS] Backup directory exists: {BACKUP_DIR}")

    # 3. Disconnected Local Backup Creation
    print("\n" + "-" * 70)
    print("CHECK 3: Disconnected Backup Creation (sync_to_cloud=False)")
    print("-" * 70)
    res = await backup_system.create_backup(sync_to_cloud=False)
    assert res is not None
    assert res["status"] == "verified"
    assert res["cloud_replicated"] is False
    assert Path(res["local_path"]).exists()
    print(f"[PASS] Created local-only backup package: {res['backup_id']} ({res['size_bytes']} bytes).")

    # 4. Manifest Integrity
    manifest = backup_system.list_backups()
    assert len(manifest) >= 1
    assert any(m["backup_id"] == res["backup_id"] for m in manifest)
    print(f"[PASS] Manifest contains {len(manifest)} recorded backup entries.")

    duration = time.time() - start_time
    print(f"\nExecution Duration: {duration:.2f}s")
    print("=" * 80)
    print("FALLBACK & RESILIENCE AUDIT PASSED 100%.")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_fallback_suite())

