"""
PRAVISION — Production Live End-to-End Universal OSINT Verification Suite
Tests the live production deployment at https://pravision.pages.dev
"""

import sys
import os
import json
import urllib.request
import urllib.error
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "backend"))

from app.auth.auth_service import get_env_auth_credentials

PROD_BASE = "https://pravision.pages.dev/api"

PASSED = 0
FAILED = 0

def check(title: str, condition: bool, details: str = ""):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  [PASS] {title} {details}")
    else:
        FAILED += 1
        print(f"  [FAIL] {title} - ERROR: {details}")

def req(url: str, method: str = "GET", data: dict = None, token: str = None):
    hdrs = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PRAVISION-LiveVerify/2.5",
        "Content-Type": "application/json"
    }
    if token:
        hdrs["Authorization"] = f"Bearer {token}"

    body = json.dumps(data).encode("utf-8") if data is not None else None
    request = urllib.request.Request(url, data=body, headers=hdrs, method=method)

    try:
        with urllib.request.urlopen(request, timeout=35) as resp:
            content = resp.read().decode("utf-8")
            try:
                parsed = json.loads(content)
            except Exception:
                parsed = {"raw": content}
            return resp.status, parsed
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            parsed = json.loads(err_body)
        except Exception:
            parsed = {"raw": err_body}
        return e.code, parsed

def run_verification():
    print("=" * 78)
    print("PRAVISION PRODUCTION UNIVERSAL OSINT LIVE VERIFICATION")
    print(f"Endpoint: {PROD_BASE}")
    print("=" * 78)

    cfg_user, cfg_pwd, _ = get_env_auth_credentials()
    assert cfg_user and cfg_pwd, "Credentials required in .env"

    # Step 1: Mandatory Auth Check on Universal Endpoint
    code, data = req(f"{PROD_BASE}/investigate/universal", method="POST", data={"query": "test@gmail.com"})
    check("Step 01: Unauthenticated request rejected with HTTP 401", code == 401, f"(HTTP {code}: {data.get('detail')})")

    # Step 2: Login to Production
    code, data = req(f"{PROD_BASE}/auth/login", method="POST", data={"username": cfg_user, "password": cfg_pwd})
    check("Step 02: Platform administrator authentication", code == 200, f"(Role: {data.get('user', {}).get('role')})")
    token = data.get("access_token")
    assert token, "Access token must be returned on login"

    # Step 3: Session check
    code, data = req(f"{PROD_BASE}/auth/session", method="GET", token=token)
    check("Step 03: Active session endpoint verified", code == 200 and data.get("authenticated") is True, f"(User: {data.get('user', {}).get('username')})")

    # Step 4: Live Email Investigation (security@google.com)
    print("\n--- Testing Live Email Investigation ---")
    code, data = req(f"{PROD_BASE}/investigate/universal", method="POST", data={"query": "security@google.com", "type": "email"}, token=token)
    check("Step 04: Email investigation returns HTTP 200", code == 200, f"(Execution: {data.get('duration_seconds')}s)")
    check("Step 05: Email status is 'completed'", data.get("status") == "completed", f"(Status: {data.get('status')})")
    identified = data.get("identified_information", {})
    check("Step 06: Email provider classified as Google Workspace / Gmail", "Google" in identified.get("Mail Provider Classification", ""), f"(Provider: {identified.get('Mail Provider Classification')})")
    check("Step 07: MX hosts successfully resolved", bool(identified.get("MX Records")), f"(MX: {identified.get('MX Records')})")
    check("Step 08: Investigation limitations clearly stated", len(data.get("investigation_limitations", [])) >= 1, f"({len(data.get('investigation_limitations', []))} limitation clauses)")
    email_job_id = data.get("id")

    # Step 5: Live Phone Number Investigation without '+' (14155552671)
    print("\n--- Testing Live Phone Number Investigation ---")
    code, data = req(f"{PROD_BASE}/investigate/universal", method="POST", data={"query": "14155552671", "type": "phone"}, token=token)
    check("Step 09: Phone investigation returns HTTP 200", code == 200, f"(Execution: {data.get('duration_seconds')}s)")
    check("Step 10: Phone normalized to E.164 +14155552671", data.get("identified_information", {}).get("E.164 Format") == "+14155552671", f"(E.164: {data.get('identified_information', {}).get('E.164 Format')})")
    check("Step 11: Geographic allocation resolved (San Francisco, CA)", "San Francisco" in data.get("identified_information", {}).get("Telecommunications Region", ""), f"(Region: {data.get('identified_information', {}).get('Telecommunications Region')})")
    check("Step 12: Line type classified", bool(data.get("identified_information", {}).get("Line Type")), f"(Line Type: {data.get('identified_information', {}).get('Line Type')})")
    check("Step 13: Timezone mapped to America/Los_Angeles", "America/Los_Angeles" in data.get("identified_information", {}).get("Timezones", ""), f"(Timezones: {data.get('identified_information', {}).get('Timezones')})")

    # Step 6: Live Username Investigation (torvalds)
    print("\n--- Testing Live Username Investigation ---")
    code, data = req(f"{PROD_BASE}/investigate/universal", method="POST", data={"query": "torvalds", "type": "username"}, token=token)
    check("Step 14: Username investigation returns HTTP 200", code == 200, f"(Execution: {data.get('duration_seconds')}s)")
    check("Step 15: Public profiles discovered across networks", len(data.get("associated_profiles", [])) >= 1, f"(Profiles: {len(data.get('associated_profiles', []))})")

    # Step 7: Retrieve Job by ID
    print("\n--- Testing Job Retrieval & History Endpoints ---")
    code, data = req(f"{PROD_BASE}/investigate/jobs/{email_job_id}", method="GET", token=token)
    check("Step 16: Retrieve completed job by ID", code == 200 and data.get("id") == email_job_id, f"(Job ID: {email_job_id})")

    # Step 8: Recent History
    code, data = req(f"{PROD_BASE}/investigate/history", method="GET", token=token)
    check("Step 17: Investigation history endpoint returns recent queries", code == 200 and len(data.get("history", [])) >= 1, f"({len(data.get('history', []))} recent queries)")

    print("\n" + "=" * 78)
    print(f"LIVE VERIFICATION RESULT: {PASSED} PASSED, {FAILED} FAILED")
    print("=" * 78)

    if FAILED > 0:
        sys.exit(1)

if __name__ == "__main__":
    run_verification()

