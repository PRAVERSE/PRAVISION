import httpx
import hashlib
import uuid

BASE_URL = "http://127.0.0.1:8000"

def test_live_app_neon_services():
    print("=" * 80)
    print("TESTING LIVE RUNNING PRAVISION APP ON NEON SERVICES (HTTP)")
    print("=" * 80)

    client = httpx.Client(timeout=15.0)

    # 1. Test Static SPA Serving
    print("\n[TEST 1] Testing SPA Frontend Serving (GET /)...")
    resp = client.get(f"{BASE_URL}/")
    print(f"Status: {resp.status_code}, Content-Type: {resp.headers.get('content-type')}")
    assert resp.status_code == 200
    assert "<!DOCTYPE html>" in resp.text or "<!doctype html>" in resp.text
    print("Verified: Frontend production bundle served successfully.")

    # 2. Test Storage Status (Neon Postgres & Neon Object Storage)
    print("\n[TEST 2] Testing Storage Status Endpoint (GET /api/storage/status)...")
    resp = client.get(f"{BASE_URL}/api/storage/status")
    print(f"Status: {resp.status_code}")
    data = resp.json()
    print("Storage Status Payload:", data)
    assert resp.status_code == 200
    
    db_info = data.get("database", {})
    assert db_info.get("status") == "healthy", f"Database not healthy: {db_info}"
    assert "Neon" in db_info.get("backend", ""), f"Backend not Neon: {db_info.get('backend')}"
    print(f"Verified: Neon Lakebase Postgres is healthy (Backend: '{db_info.get('backend')}', Latency: {db_info.get('latency_ms')}ms)")

    obj_info = data.get("object_storage", {})
    assert obj_info.get("cloud_enabled") is True
    assert "Neon" in obj_info.get("storage_mode", "")
    assert obj_info.get("bucket") == "pravision-evidence"
    print(f"Verified: Neon Object Storage is active (Mode: '{obj_info.get('storage_mode')}', Bucket: '{obj_info.get('bucket')}')")

    # 3. Test Creating a Case in Neon Postgres via Live API
    print("\n[TEST 3] Creating a Case in Neon Postgres (POST /api/cases)...")
    case_payload = {
        "title": f"Live Neon App Case - {uuid.uuid4().hex[:6]}",
        "description": "Created through live HTTP API to verify Neon Postgres persistence",
        "created_by": "Neon Verification Agent",
        "classification": "CONFIDENTIAL",
        "tags": ["live_api_test", "neon_postgres"]
    }
    resp = client.post(f"{BASE_URL}/api/cases", json=case_payload)
    print(f"Status: {resp.status_code}")
    assert resp.status_code == 200
    created_case = resp.json()
    case_id = created_case["id"]
    print(f"Verified: Created Case in Neon Postgres (ID: {case_id}, Number: {created_case.get('case_number')})")

    # 4. Test Uploading Evidence to Neon Object Storage via Live API
    print("\n[TEST 4] Uploading Evidence to Neon Object Storage (POST /api/storage/evidence/upload)...")
    sample_content = b"LIVE PRAVISION TELEMETRY FILE // NEON S3 OBJECT STORAGE " + uuid.uuid4().bytes
    expected_sha256 = hashlib.sha256(sample_content).hexdigest()
    
    files = {
        "file": ("live_intel_report.txt", sample_content, "text/plain")
    }
    data_form = {
        "investigation_id": case_id
    }
    resp = client.post(f"{BASE_URL}/api/storage/evidence/upload", files=files, data=data_form)
    print(f"Status: {resp.status_code}")
    assert resp.status_code == 200
    upload_res = resp.json()
    print("Upload Response:", upload_res)
    assert upload_res.get("storage_backend") == "neon_cloud"
    assert upload_res.get("file_hash") == expected_sha256
    file_key = upload_res.get("file_key")
    print(f"Verified: Uploaded directly to Neon Object Storage with SHA-256 {expected_sha256}")

    # 5. Test Downloading Evidence from Neon Object Storage via Live API
    print(f"\n[TEST 5] Downloading Evidence from Neon Object Storage (GET /api/storage/evidence/{file_key})...")
    resp = client.get(f"{BASE_URL}/api/storage/evidence/{file_key}")
    print(f"Status: {resp.status_code}")
    assert resp.status_code == 200
    downloaded_data = resp.content
    assert hashlib.sha256(downloaded_data).hexdigest() == expected_sha256
    assert downloaded_data == sample_content
    print(f"Verified: Downloaded file from Neon Object Storage matches original bit-for-bit!")

    # 6. Test Case Retrieval from Neon Postgres
    print(f"\n[TEST 6] Querying Case from Neon Postgres (GET /api/cases/{case_id})...")
    resp = client.get(f"{BASE_URL}/api/cases/{case_id}")
    assert resp.status_code == 200
    queried_case = resp.json()
    assert queried_case["id"] == case_id
    assert queried_case["title"] == case_payload["title"]
    print("Verified: Case successfully fetched from Neon Postgres.")

    # 7. Clean up Case in Neon Postgres
    print(f"\n[TEST 7] Deleting Case in Neon Postgres (DELETE /api/cases/{case_id})...")
    resp = client.delete(f"{BASE_URL}/api/cases/{case_id}")
    assert resp.status_code == 200
    print("Verified: Case deleted from Neon Postgres.")

    print("\n" + "=" * 80)
    print("END-TO-END LIVE APP NEON INTEGRATION TEST COMPLETED SUCCESSFULLY!")
    print("=" * 80)

if __name__ == "__main__":
    test_live_app_neon_services()
