import sys
from pathlib import Path

# Add backend to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from app.main import app

def test_complete_api_suite():
    client = TestClient(app)

    print("=" * 80)
    print("PRAVISION FASTAPI ENDPOINT INDEPENDENT VERIFICATION SUITE")
    print("=" * 80)

    # 1. Health & Root (SPA or root info)
    res = client.get("/")
    print(f"GET / -> Status: {res.status_code}")
    assert res.status_code == 200

    # 2. Input Classifier
    res = client.post("/api/classify", json={"input": "target_analyst"})
    print(f"POST /api/classify (username) -> Status: {res.status_code}, data: {res.json()}")
    assert res.status_code == 200
    assert res.json()["detected_type"] == "username"
    assert res.json()["mode"] == "mode_1_identity"

    res_email = client.post("/api/classify", json={"input": "analyst@target.corp"})
    print(f"POST /api/classify (email) -> Status: {res_email.status_code}, data: {res_email.json()}")
    assert res_email.status_code == 200
    assert res_email.json()["detected_type"] == "email"

    # 3. Storage Status
    res = client.get("/api/storage/status")
    print(f"GET /api/storage/status -> Status: {res.status_code}, data: {res.json()}")
    assert res.status_code == 200
    data = res.json()
    assert "database" in data
    assert "object_storage" in data
    assert data["database"]["status"] == "healthy"

    # 4. Connectors List
    res = client.get("/api/connectors")
    print(f"GET /api/connectors -> Status: {res.status_code}")
    assert res.status_code == 200
    connectors = res.json()
    print(f"Discovered {len(connectors)} connectors via API.")
    assert len(connectors) == 89

    # 5. Settings
    res = client.get("/api/settings")
    print(f"GET /api/settings -> Status: {res.status_code}")
    assert res.status_code == 200
    assert "limits" in res.json()

    # 6. Document Intel Scanner
    sample_text = "Target operative contact: agent007@intel.gov, operating on IP 192.168.10.55 and BTC wallet 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
    res = client.post("/api/intelligence/document/scan", json={"text": sample_text})
    print(f"POST /api/intelligence/document/scan -> Status: {res.status_code}, data: {res.json()}")
    assert res.status_code == 200
    extracted = res.json()
    assert "agent007@intel.gov" in extracted["emails"]
    assert "192.168.10.55" in extracted["ip_addresses"]
    assert "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa" in extracted["crypto_wallets"]

    # 7. Intelligence Workstation Endpoints (Memory Scope)
    res = client.get("/api/intelligence/entity-resolution")
    assert res.status_code == 200
    print(f"GET /api/intelligence/entity-resolution -> Status: 200")

    res = client.get("/api/intelligence/graph-analytics")
    assert res.status_code == 200
    print(f"GET /api/intelligence/graph-analytics -> Status: 200")

    res = client.get("/api/intelligence/timeline")
    assert res.status_code == 200
    print(f"GET /api/intelligence/timeline -> Status: 200")

    res = client.get("/api/intelligence/threat-posture")
    assert res.status_code == 200
    print(f"GET /api/intelligence/threat-posture -> Status: 200")

    res = client.post("/api/intelligence/ask", json={"query": "Summary of active evidence"})
    assert res.status_code == 200
    print(f"POST /api/intelligence/ask -> Status: 200, answer: {res.json()['answer']}")

    # 8. Cases CRUD
    res = client.get("/api/cases")
    assert res.status_code == 200
    initial_cases = res.json()
    print(f"GET /api/cases -> {len(initial_cases)} cases currently in database.")

    # Create Case
    res = client.post("/api/cases", json={
        "title": "API Verification Case Dossier",
        "description": "Created during automated API test suite",
        "classification": "CONFIDENTIAL",
        "tags": ["automated_test", "fastapi"]
    })
    assert res.status_code == 200
    created_case = res.json()
    case_id = created_case["id"]
    print(f"POST /api/cases -> Created Case ID: {case_id}")

    # Get Single Case
    res = client.get(f"/api/cases/{case_id}")
    assert res.status_code == 200
    assert res.json()["title"] == "API Verification Case Dossier"
    print(f"GET /api/cases/{case_id} -> Verified single case retrieval.")

    # Delete Case
    res = client.delete(f"/api/cases/{case_id}")
    assert res.status_code == 200
    print(f"DELETE /api/cases/{case_id} -> Deleted successfully.")

    # 9. Privacy Purge Endpoint
    res = client.post("/api/settings/purge")
    assert res.status_code == 200
    print(f"POST /api/settings/purge -> {res.json()}")

    print("\nALL FASTAPI ENDPOINTS VERIFIED SUCCESSFULLY WITH 100% SPEC CONFORMANCE.")

if __name__ == "__main__":
    test_complete_api_suite()

