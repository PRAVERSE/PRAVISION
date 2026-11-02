import asyncio
import os
import sys
import time
import httpx
from pathlib import Path

# Add backend to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.main import app
from app.storage.database import init_db

async def test_api_regression_suite():
    print("=" * 80)
    print("PRAVISION PHASE 2.4 — API ENDPOINTS & BACKUP SUITE REGRESSION")
    print("=" * 80)
    start_time = time.time()

    await init_db()

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # 1. Classification
        res_class = await client.post("/api/classify", json={"input": "test.target@example.org"})
        assert res_class.status_code == 200
        assert res_class.json()["detected_type"] == "email"
        print("[PASS] POST /api/classify operational.")

        # 2. Connectors
        res_conn = await client.get("/api/connectors")
        assert res_conn.status_code == 200
        assert len(res_conn.json()) >= 10
        print(f"[PASS] GET /api/connectors returned {len(res_conn.json())} connectors.")

        # 3. Storage Status
        res_stor = await client.get("/api/storage/status")
        assert res_stor.status_code == 200
        assert "database" in res_stor.json()
        assert "object_storage" in res_stor.json()
        print("[PASS] GET /api/storage/status operational.")

        # 4. Backup Status
        res_b_stat = await client.get("/api/backup/status")
        assert res_b_stat.status_code == 200
        b_stat = res_b_stat.json()
        assert "scheduler_running" in b_stat
        assert "interval_seconds" in b_stat
        print(f"[PASS] GET /api/backup/status operational: {b_stat}")

        # 5. Backup History
        res_b_hist = await client.get("/api/backup/history")
        assert res_b_hist.status_code == 200
        print(f"[PASS] GET /api/backup/history returned {len(res_b_hist.json())} historical records.")

        # 6. Trigger Backup via API
        res_b_run = await client.post("/api/backup/run", json={"sync_cloud": False})
        assert res_b_run.status_code == 200
        bkp_entry = res_b_run.json()
        assert "backup_id" in bkp_entry
        backup_id = bkp_entry["backup_id"]
        print(f"[PASS] POST /api/backup/run created backup {backup_id}.")

        # 7. Download Backup Package via API
        res_b_dl = await client.get(f"/api/backup/download/{backup_id}")
        assert res_b_dl.status_code == 200
        assert res_b_dl.content.startswith(b"PVBKP\x02")
        print(f"[PASS] GET /api/backup/download/{backup_id} downloaded {len(res_b_dl.content)} bytes.")

        # 8. Restore Verification via API
        files = {
            "file": (f"{backup_id}.pravision_bkp", res_b_dl.content, "application/octet-stream")
        }
        data = {
            "verify_only": "true",
            "prefix": "API_TEST_"
        }
        res_b_rest = await client.post("/api/backup/restore", files=files, data=data)
        assert res_b_rest.status_code == 200
        rest_info = res_b_rest.json()
        assert rest_info["status"] == "verified"
        assert rest_info["backup_id"] == backup_id
        print(f"[PASS] POST /api/backup/restore (dry-run) verified successfully: {rest_info}")

    duration = time.time() - start_time
    print(f"\nExecution Duration: {duration:.2f}s")
    print("=" * 80)
    print("PHASE 2.4 API REGRESSION SUITE: 100% PASSED")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_api_regression_suite())

