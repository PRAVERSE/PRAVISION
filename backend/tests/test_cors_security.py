"""
PRAVISION — CORS Security Verification Test
Verifies that only exact production origin is accepted and that arbitrary
or unrelated *.pages.dev origins are strictly rejected.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient
from app.main import app

def test_cors_allowlist():
    client = TestClient(app)

    # 1. Exact Production Origin should be allowed
    resp_valid = client.options(
        "/api/storage/status",
        headers={
            "Origin": "https://pravision.pages.dev",
            "Access-Control-Request-Method": "GET"
        }
    )
    assert resp_valid.headers.get("access-control-allow-origin") == "https://pravision.pages.dev", \
        f"Production origin must be allowed. Got: {resp_valid.headers.get('access-control-allow-origin')}"
    print("[PASS] Exact production origin 'https://pravision.pages.dev' is ALLOWED.")

    # 2. Unrelated / malicious *.pages.dev origin should be REJECTED
    resp_unrelated = client.options(
        "/api/storage/status",
        headers={
            "Origin": "https://attacker-project.pages.dev",
            "Access-Control-Request-Method": "GET"
        }
    )
    assert resp_unrelated.headers.get("access-control-allow-origin") is None, \
        f"Unrelated pages.dev origin must be REJECTED. Got: {resp_unrelated.headers.get('access-control-allow-origin')}"
    print("[PASS] Unrelated 'https://attacker-project.pages.dev' is strictly REJECTED.")

    # 3. Arbitrary untrusted origin should be REJECTED
    resp_evil = client.options(
        "/api/storage/status",
        headers={
            "Origin": "https://evil-hacker.com",
            "Access-Control-Request-Method": "GET"
        }
    )
    assert resp_evil.headers.get("access-control-allow-origin") is None, \
        f"Arbitrary origin must be REJECTED. Got: {resp_evil.headers.get('access-control-allow-origin')}"
    print("[PASS] Arbitrary origin 'https://evil-hacker.com' is strictly REJECTED.")

if __name__ == "__main__":
    test_cors_allowlist()
    print("ALL CORS SECURITY TESTS PASSED.")
