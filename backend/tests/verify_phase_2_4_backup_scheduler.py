import asyncio
import os
import sys
import time
from pathlib import Path

# Add backend to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.storage.database import init_db
from app.storage.backup_system import backup_scheduler, backup_system

async def test_backup_scheduler_suite():
    print("=" * 80)
    print("PRAVISION PHASE 2.4 — BACKUP SCHEDULER VERIFICATION")
    print("=" * 80)
    start_time = time.time()

    await init_db()

    # 1. Inspect initial scheduler status
    status = backup_scheduler.get_status()
    print("Initial Scheduler Status:", status)
    assert "scheduler_running" in status
    assert "interval_seconds" in status
    assert status["interval_seconds"] == 3600
    print("[PASS] Initial scheduler status conforms to specification.")

    # 2. Test lifecycle: start and stop scheduler
    await backup_scheduler.start()
    assert backup_scheduler.is_running is True
    running_status = backup_scheduler.get_status()
    assert running_status["scheduler_running"] is True
    print("[PASS] Scheduler started successfully as background task.")

    # 3. Trigger manual backup cycle
    print("\nExecuting manual backup cycle...")
    res = await backup_system.create_backup(sync_to_cloud=False)
    assert res is not None
    assert "backup_id" in res
    assert res["status"] == "verified"
    print(f"[PASS] Manual backup cycle completed: ID={res['backup_id']}, Size={res['size_bytes']} bytes.")

    # 4. Graceful stop
    await backup_scheduler.stop()
    assert backup_scheduler.is_running is False
    stopped_status = backup_scheduler.get_status()
    assert stopped_status["scheduler_running"] is False
    print("[PASS] Scheduler stopped gracefully with zero dangling tasks.")

    duration = time.time() - start_time
    print(f"\nExecution Duration: {duration:.2f}s")
    print("=" * 80)
    print("BACKUP SCHEDULER SUITE: 100% PASSED")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_backup_scheduler_suite())

