"""
PRAVISION — Health Endpoint Security & Information Leakage Verification Test
Verifies that the public health endpoint strictly returns minimal operational liveness
and contains zero infrastructure hostnames, filesystem paths, buckets, or metrics.
Verifies that detailed diagnostics require Admin role.
"""

import sys
import json
import urllib.request
import urllib.error
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.auth.auth_service import create_jwt_token

BASE_URL = "http://127.0.0.1:8000/api"

def test_health_endpoint_hardening():
    # 1. Test public unauthenticated liveness endpoint
    req = urllib.request.Request(f"{BASE_URL}/storage/status")
    with urllib.request.urlopen(req, timeout=10) as resp:
        status_code = resp.status
        raw_body = resp.read().decode("utf-8")
        data = json.loads(raw_body)
        raw_text = raw_body.lower()

    assert status_code == 200, f"Expected 200, got {status_code}"
    assert data.get("status") in ("healthy", "ok"), "Must have healthy status"
    assert "database" in data, "Must have database status"
    assert "storage" in data, "Must have storage status"

    # Verify ZERO leakage of sensitive infrastructure
    forbidden_terms = [
        "c:\\", "c:/", "/home/", "/app/", "vault_path", "evidence_vault",
        "neon.tech", "postgres://", "postgresql+", "@ep-", "aws.neon.tech",
        "pravision-evidence", "s3.ap-southeast", "b2_bucket", "bucket_name",
        "local_vault_size_bytes", "local_vault_file_count", "database_url"
    ]
    for term in forbidden_terms:
        assert term not in raw_text, f"Security Leakage detected: '{term}' found in public health response: {raw_body}"
    print("[PASS] Public health endpoint returns minimal liveness and leaks ZERO infrastructure details.")

    # 2. Test diagnostics endpoint without auth -> 401 Unauthorized
    req_diag_unauth = urllib.request.Request(f"{BASE_URL}/storage/diagnostics")
    try:
        urllib.request.urlopen(req_diag_unauth, timeout=10)
        assert False, "Unauthenticated diagnostics request must raise HTTPError"
    except urllib.error.HTTPError as e:
        assert e.code in (401, 403), f"Expected 401/403, got {e.code}"
        print(f"[PASS] Unauthenticated access to /api/storage/diagnostics is REJECTED (HTTP {e.code}).")

    # 3. Test diagnostics endpoint with non-admin (Analyst) -> 403 Forbidden
    analyst_token = create_jwt_token("349796b7-2926-4234-aa81-d3015bab3d6e", "analyst", "analyst")
    req_diag_analyst = urllib.request.Request(
        f"{BASE_URL}/storage/diagnostics",
        headers={"Authorization": f"Bearer {analyst_token}"}
    )
    try:
        urllib.request.urlopen(req_diag_analyst, timeout=10)
        assert False, "Analyst access to diagnostics must raise HTTPError"
    except urllib.error.HTTPError as e:
        assert e.code == 403, f"Expected 403 Forbidden for Analyst, got {e.code}"
        print(f"[PASS] Non-admin (Analyst) access to /api/storage/diagnostics is REJECTED (HTTP {e.code} Forbidden).")

    # 4. Test diagnostics endpoint with Admin -> 200 OK
    admin_token = create_jwt_token("4500f6d3-4e92-439e-80ec-f731ebac9402", "admin", "admin")
    req_diag_admin = urllib.request.Request(
        f"{BASE_URL}/storage/diagnostics",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    with urllib.request.urlopen(req_diag_admin, timeout=10) as admin_resp:
        assert admin_resp.status == 200, f"Admin must receive 200, got {admin_resp.status}"
        diag_data = json.loads(admin_resp.read().decode())
        assert "database" in diag_data, "Diagnostics must include database diagnostics"
        assert "object_storage" in diag_data, "Diagnostics must include object storage diagnostics"
        print(f"[PASS] Admin role successfully retrieves /api/storage/diagnostics (HTTP {admin_resp.status}).")

if __name__ == "__main__":
    test_health_endpoint_hardening()
    print("ALL HEALTH ENDPOINT HARDENING TESTS PASSED.")
