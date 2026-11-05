"""
PRAVISION — Backend Restart Persistence Verification Suite
Explicitly proves that:
1. Token revocation survives an actual Uvicorn backend process termination & restart.
2. IP rate-limiting lockout survives an actual Uvicorn backend process termination & restart.
3. Protected routes strictly reject replayed revoked tokens post-restart with HTTP 401.
4. Locked out IPs remain locked out post-restart with HTTP 429.
"""

import os
import sys
import time
import json
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.auth.auth_service import get_env_auth_credentials

LOCAL_API = "http://127.0.0.1:8000/api"
PASSED = 0
FAILED = 0

def check(name: str, cond: bool, msg: str = ""):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  [PASS] {name} {msg}")
    else:
        FAILED += 1
        print(f"  [FAIL] {name} - ERROR: {msg}")

def http_req(method: str, url: str, data: dict = None, headers: dict = None) -> tuple[int, dict]:
    hdrs = {
        "User-Agent": "PRAVISION-RestartTest/1.0",
        "Content-Type": "application/json",
        "Connection": "close"
    }
    if headers:
        hdrs.update(headers)
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read().decode("utf-8")
            return resp.status, json.loads(content) if content else {}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            err_json = json.loads(err_body)
        except Exception:
            err_json = {"detail": err_body}
        return e.code, err_json

def find_uvicorn_pid() -> int:
    try:
        out = subprocess.check_output('netstat -ano | findstr :8000', shell=True).decode()
        for line in out.strip().splitlines():
            parts = line.split()
            if len(parts) >= 5 and "LISTENING" in parts:
                return int(parts[-1])
    except Exception:
        pass
    return 0

def kill_process(pid: int):
    subprocess.run(f"taskkill /F /PID {pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def wait_for_backend(timeout: int = 75) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            code, data = http_req("GET", f"{LOCAL_API}/storage/status")
            if code == 200 and data.get("status") == "healthy":
                return True
        except Exception:
            pass
        time.sleep(1)
    return False

def run_restart_persistence_test():
    print("=" * 75)
    print("PRAVISION BACKEND PROCESS RESTART PERSISTENCE AUDIT")
    print("=" * 75)

    env_user, env_pwd, _ = get_env_auth_credentials()
    if not env_user or not env_pwd:
        print("  [ERROR] .env credentials missing.")
        sys.exit(1)

    # 1. Authenticate to get a valid token
    code, data = http_req("POST", f"{LOCAL_API}/auth/login", {"username": env_user, "password": env_pwd})
    check("Pre-Restart Login Successful", code == 200 and "access_token" in data)
    token = data.get("access_token")

    # 2. Verify token works against protected endpoint
    c_code, c_data = http_req("GET", f"{LOCAL_API}/cases", headers={"Authorization": f"Bearer {token}"})
    check("Pre-Restart Token Authorized on Protected Endpoint", c_code == 200 and isinstance(c_data, list))

    # 3. Log out to revoke the token
    l_code, l_data = http_req("POST", f"{LOCAL_API}/auth/logout", headers={"Authorization": f"Bearer {token}"})
    check("Pre-Restart Logout & Revocation Successful", l_code == 200 and l_data.get("status") == "logged_out")

    # 4. Verify token is immediately rejected
    rej_code, rej_data = http_req("GET", f"{LOCAL_API}/cases", headers={"Authorization": f"Bearer {token}"})
    check("Pre-Restart Immediate Rejection of Revoked Token", rej_code == 401)

    # 5. Lock out a test IP address
    test_ip = f"198.51.100.{int(time.time()) % 150 + 20}"
    ip_headers = {"X-Forwarded-For": test_ip}
    for _ in range(5):
        http_req("POST", f"{LOCAL_API}/auth/login", {"username": "attacker", "password": "bad"}, headers=ip_headers)
    lock_code, lock_data = http_req("POST", f"{LOCAL_API}/auth/login", {"username": "attacker", "password": "bad"}, headers=ip_headers)
    check("Pre-Restart IP Lockout Active (HTTP 429)", lock_code == 429)

    # 6. Locate Uvicorn backend process and FORCIBLY TERMINATE IT
    uvicorn_pid = find_uvicorn_pid()
    check("Found Running Backend Uvicorn Process", uvicorn_pid > 0, f"(PID: {uvicorn_pid})")

    if uvicorn_pid > 0:
        print(f"  [ACTION] Terminating Uvicorn PID {uvicorn_pid} to trigger supervisor restart...")
        kill_process(uvicorn_pid)

    # 7. Wait for Watchdog to revive the backend
    print("  [WAIT] Waiting for watchdog supervisor to restart backend...")
    restarted = wait_for_backend(timeout=35)
    new_pid = find_uvicorn_pid()
    check("Backend Resurrected by Watchdog", restarted and new_pid > 0 and new_pid != uvicorn_pid, f"(Old PID: {uvicorn_pid} -> New PID: {new_pid})")

    # 8. Post-Restart Token Revocation Anti-Replay Verification
    post_c_code, post_c_data = http_req("GET", f"{LOCAL_API}/cases", headers={"Authorization": f"Bearer {token}"})
    check(
        "POST-RESTART: Revoked Token Strictly Rejected (Anti-Replay Confirmed)",
        post_c_code == 401,
        f"(HTTP {post_c_code}: {post_c_data.get('detail')})"
    )

    # 9. Post-Restart IP Lockout Persistence Verification
    post_lock_code, post_lock_data = http_req("POST", f"{LOCAL_API}/auth/login", {"username": "attacker", "password": "bad"}, headers=ip_headers)
    check(
        "POST-RESTART: IP Lockout Persists in PostgreSQL (HTTP 429 Confirmed)",
        post_lock_code == 429,
        f"(HTTP {post_lock_code}: {post_lock_data.get('detail')})"
    )

    # 10. Fresh login succeeds with clean credentials on restarted backend
    fresh_code, fresh_data = http_req("POST", f"{LOCAL_API}/auth/login", {"username": env_user, "password": env_pwd})
    check("POST-RESTART: Fresh Valid Login Allowed", fresh_code == 200 and "access_token" in fresh_data)

    print("=" * 75)
    print(f"RESTART PERSISTENCE TEST RESULTS: {PASSED} PASSED, {FAILED} FAILED")
    print("=" * 75)
    if FAILED > 0:
        sys.exit(1)

if __name__ == "__main__":
    run_restart_persistence_test()
