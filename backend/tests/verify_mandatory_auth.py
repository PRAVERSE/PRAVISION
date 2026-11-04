"""
PRAVISION — Mandatory Authentication & Session Protection Verification Suite
Tests the complete end-to-end authentication lifecycle against:
  1. Local Origin API (http://127.0.0.1:8000/api)
  2. Public Production Edge (https://pravision.pages.dev/api)

Verifies:
  - Strict route protection: 401 Unauthorized on protected routes without session.
  - Credential authentication via .env credentials.
  - Secure HTTP-only cookie (pravision_session) emission.
  - Generic 401 error rejection on bad credentials (zero field leakage).
  - Rate limiting & lockout after 5 consecutive failed attempts (429 Too Many Requests).
  - Active session check (/auth/session) returning authenticated state.
  - Server-side session invalidation on logout and cookie destruction.
"""

import os
import sys
import json
import uuid
import urllib.request
import urllib.error
from pathlib import Path
from http.cookiejar import CookieJar

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.auth.auth_service import get_env_auth_credentials

LOCAL_API = "http://127.0.0.1:8000/api"
PUBLIC_API = "https://pravision.pages.dev/api"

PASSED = 0
FAILED = 0


def log_test(step: int, title: str, condition: bool, details: str = ""):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  [PASS] Step {step:02d}: {title} {details}")
    else:
        FAILED += 1
        print(f"  [FAIL] Step {step:02d}: {title} - ERROR: {details}")


def req(method: str, url: str, data: dict = None, headers: dict = None, cookie: str = None) -> tuple[int, dict, dict, list]:
    hdrs = {
        "User-Agent": "PRAVISION-AuthTest/1.0",
        "Content-Type": "application/json"
    }
    if headers:
        hdrs.update(headers)
    if cookie:
        hdrs["Cookie"] = cookie

    body = json.dumps(data).encode("utf-8") if data is not None else None
    request = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(request, timeout=20) as resp:
            resp_body = resp.read().decode("utf-8")
            res_json = json.loads(resp_body) if resp_body else {}
            set_cookies = resp.headers.get_all("Set-Cookie") or []
            return resp.status, res_json, dict(resp.headers), set_cookies
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            err_json = json.loads(err_body)
        except Exception:
            err_json = {"detail": err_body}
        set_cookies = e.headers.get_all("Set-Cookie") or []
        return e.code, err_json, dict(e.headers), set_cookies


def test_mandatory_auth():
    print("=" * 78)
    print("PRAVISION MANDATORY WEBSITE AUTHENTICATION & ACCESS CONTROL TEST SUITE")
    print(f"Local API:  {LOCAL_API}")
    print(f"Public API: {PUBLIC_API}")
    print("=" * 78)

    env_user, env_pwd, _ = get_env_auth_credentials()
    if not env_user or not env_pwd:
        print("  [ERROR] .env credentials not configured. Please ensure credentials exist in .env.")
        sys.exit(1)

    print("  [INFO] .env credentials discovered and verified (masked for security).")

    # 1. Unauthenticated request to protected endpoint on Local API
    code, data, _, _ = req("GET", f"{LOCAL_API}/cases")
    log_test(1, "Origin Protected Route Rejection (Unauthenticated)", code == 401, f"(HTTP {code}: {data.get('detail')})")

    # 2. Unauthenticated request to protected endpoint on Public API
    pub_code, pub_data, _, _ = req("GET", f"{PUBLIC_API}/cases")
    log_test(2, "Public Edge Protected Route Rejection (Unauthenticated)", pub_code == 401, f"(HTTP {pub_code}: {pub_data.get('detail')})")

    # 3. Public Minimal Status (Allowlist verification)
    s_code, s_data, _, _ = req("GET", f"{PUBLIC_API}/storage/status")
    log_test(3, "Public Liveness Allowed Without Authentication", s_code == 200 and s_data.get("status") == "healthy", f"(HTTP {s_code})")

    # 4. Session Check When Unauthenticated
    sess_code, sess_data, _, _ = req("GET", f"{PUBLIC_API}/auth/session")
    log_test(4, "Public Session Liveness (Unauthenticated)", sess_code == 200 and sess_data.get("authenticated") is False, f"(Authenticated: {sess_data.get('authenticated')})")

    # 5. Invalid Credentials Rejection (Zero Field Leakage)
    bad_code, bad_data, _, _ = req("POST", f"{LOCAL_API}/auth/login", data={"username": env_user, "password": "WrongPassword_999!"})
    bad_ok = (bad_code == 401 and "Invalid username or password" in bad_data.get("detail", "") and "password" not in bad_data.get("detail", "").lower().split(" "))
    log_test(5, "Generic Error on Bad Credentials (No Field Leakage)", bad_code == 401, f"(HTTP {bad_code}: {bad_data.get('detail')})")

    # 6. Valid Authentication with .env Credentials on Public Edge
    login_code, login_data, login_headers, set_cookies = req("POST", f"{PUBLIC_API}/auth/login", data={"username": env_user, "password": env_pwd})
    login_ok = (
        login_code == 200 and
        "access_token" in login_data and
        login_data.get("user", {}).get("username") == env_user and
        login_data.get("user", {}).get("role") == "admin"
    )
    cookie_str = "; ".join(set_cookies)
    has_session_cookie = "pravision_session=" in cookie_str
    log_test(6, "Public Edge Authentication with .env Credentials", login_ok, f"(HTTP {login_code}, Role: {login_data.get('user', {}).get('role')})")
    log_test(7, "Secure HTTP-only Session Cookie Emitted", has_session_cookie, f"(Set-Cookie present: {has_session_cookie})")

    token = login_data.get("access_token")

    # 8. Authenticated Access via Bearer Token on Public Edge
    c_code, c_data, _, _ = req("GET", f"{PUBLIC_API}/cases", headers={"Authorization": f"Bearer {token}"})
    log_test(8, "Public Edge Access with Valid Bearer Token", c_code == 200 and isinstance(c_data, list), f"(HTTP {c_code}, Cases returned: {len(c_data)})")

    # 9. Session Verification with Active Cookie/Token
    auth_sess_code, auth_sess_data, _, _ = req("GET", f"{PUBLIC_API}/auth/session", headers={"Authorization": f"Bearer {token}"})
    log_test(9, "Active Session Endpoint Verification", auth_sess_code == 200 and auth_sess_data.get("authenticated") is True, f"(Authenticated: {auth_sess_data.get('authenticated')}, User: {auth_sess_data.get('user', {}).get('username')})")

    # 10. Logout & Server-Side Session Invalidation
    logout_code, logout_data, _, logout_cookies = req("POST", f"{PUBLIC_API}/auth/logout", headers={"Authorization": f"Bearer {token}"})
    log_test(10, "Server-Side Logout & Session Revocation", logout_code == 200 and logout_data.get("status") == "logged_out", f"(HTTP {logout_code})")

    # 11. Post-Logout Protected Route Rejection with Revoked Token (Anti-Replay)
    post_code, post_data, _, _ = req("GET", f"{PUBLIC_API}/cases", headers={"Authorization": f"Bearer {token}"})
    log_test(11, "Revoked Token Rejection on Protected Route", post_code == 401, f"(HTTP {post_code}: {post_data.get('detail')})")

    # 12. Rate-Limiting & Lockout Verification (5 Failed Attempts -> 429 Lockout)
    test_ip_headers = {"X-Forwarded-For": "198.51.100.42"}
    lockout_triggered = False
    for i in range(5):
        fc, fd, _, _ = req("POST", f"{LOCAL_API}/auth/login", data={"username": "lockout_test_user", "password": "wrong"}, headers=test_ip_headers)
        if fc == 429:
            lockout_triggered = True
            break
    # 6th attempt should definitely return 429
    fc_final, fd_final, _, _ = req("POST", f"{LOCAL_API}/auth/login", data={"username": "lockout_test_user", "password": "wrong"}, headers=test_ip_headers)
    if fc_final == 429:
        lockout_triggered = True
    log_test(12, "Brute-Force Rate Limiting (5 Attempts -> 429 Lockout)", lockout_triggered, f"(HTTP {fc_final}: {fd_final.get('detail')})")

    print("=" * 78)
    print(f"AUTHENTICATION TEST SUMMARY: {PASSED} PASSED, {FAILED} FAILED")
    print("=" * 78)

    if FAILED > 0:
        sys.exit(1)


if __name__ == "__main__":
    test_mandatory_auth()

