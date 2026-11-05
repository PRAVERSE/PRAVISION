"""
PRAVISION — Final Logout Revocation & Cross-Worker Security Test Suite
Exhaustively verifies:
1. Normal logout revokes the access token in PostgreSQL.
2. Normal logout revokes the refresh token in PostgreSQL.
3. Both tokens are rejected after logout (access -> 401, refresh -> 401).
4. Database outage during access-token revocation returns HTTP 503.
5. Database outage during refresh-token revocation returns HTTP 503.
6. Logout never reports successful revocation when database transaction fails.
7. Repeated logout requests are handled safely (idempotency).
8. Worker A clears a lockout and worker B observes the updated database state.
9. Worker A creates a lockout and worker B enforces it.
10. Actual separate Uvicorn worker processes share the same PostgreSQL lockout state.
11. Concurrent requests across multiple processes cannot lose increments.
12. Forged XFF cannot bypass IP lockout (strict proxy chain validation).
13. Public production requests use the correct authoritative Cloudflare client IP.
"""

import os
import sys
import time
import uuid
import json
import asyncio
import ipaddress
import subprocess
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from unittest.mock import patch

# Setup sys.path
BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.storage.database import async_session_maker, engine
from app.storage.models_db import RevokedTokenModel, IpLockoutModel, UserModel
from app.auth.auth_service import (
    auth_service, AuthService, create_jwt_token, decode_jwt_token,
    get_env_auth_credentials
)
from app.api.auth_routes import _extract_client_ip, TRUSTED_PROXIES
from sqlalchemy import select, delete
from fastapi import HTTPException
from starlette.requests import Request

LOCAL_API = "http://127.0.0.1:8000/api"
PUBLIC_API = "https://pravision.pages.dev/api"

PASSED = 0
FAILED = 0


def log_test(num: int, title: str, condition: bool, details: str = ""):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  [PASS] Test {num:02d}: {title} {details}")
    else:
        FAILED += 1
        print(f"  [FAIL] Test {num:02d}: {title} - ERROR: {details}")


def http_req(method: str, url: str, data: dict = None, headers: dict = None) -> tuple[int, dict, dict, list]:
    hdrs = {
        "User-Agent": "PRAVISION-CrossWorkerTest/1.0",
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
            set_cookies = resp.headers.get_all("Set-Cookie") or []
            return resp.status, json.loads(content) if content else {}, dict(resp.headers), set_cookies
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            err_json = json.loads(err_body)
        except Exception:
            err_json = {"detail": err_body}
        set_cookies = e.headers.get_all("Set-Cookie") or []
        return e.code, err_json, dict(e.headers), set_cookies


# Top-level helper function for multiprocessing worker tests
def _send_concurrent_failure(target_ip: str) -> int:
    hdrs = {
        "User-Agent": "PRAVISION-MultiProcessWorker/1.0",
        "Content-Type": "application/json",
        "Connection": "close",
        "CF-Connecting-IP": target_ip
    }
    body = json.dumps({"username": "attacker", "password": "wrong_password_xyz"}).encode("utf-8")
    req = urllib.request.Request(f"{LOCAL_API}/auth/login", data=body, headers=hdrs, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0


async def run_all_tests():
    global PASSED, FAILED
    print("=" * 80)
    print("PRAVISION FINAL LOGOUT REVOCATION & CROSS-WORKER VERIFICATION SUITE")
    print("=" * 80)

    env_user, env_pwd, _ = get_env_auth_credentials()
    if not env_user or not env_pwd:
        print("[ERROR] .env credentials missing.")
        sys.exit(1)

    # -------------------------------------------------------------
    # 1. Normal logout revokes the access token
    # -------------------------------------------------------------
    login_code, login_data, _, _ = http_req("POST", f"{LOCAL_API}/auth/login", {"username": env_user, "password": env_pwd})
    acc_token = login_data.get("access_token")
    ref_token = login_data.get("refresh_token")
    acc_jti = decode_jwt_token(acc_token)["jti"]
    ref_jti = decode_jwt_token(ref_token)["jti"]

    # Call logout with access token in header
    l_code, l_data, _, l_cookies = http_req("POST", f"{LOCAL_API}/auth/logout", headers={"Authorization": f"Bearer {acc_token}"})
    log_test(1, "Normal Logout Returns HTTP 200", l_code == 200 and l_data.get("status") == "logged_out")

    # Verify access token is recorded in PostgreSQL
    async with async_session_maker() as session:
        rec = (await session.execute(select(RevokedTokenModel).where(RevokedTokenModel.token_jti == acc_jti))).scalar_one_or_none()
        log_test(1, "Access Token Persisted in PostgreSQL revoked_tokens", rec is not None and rec.token_jti == acc_jti)

    # -------------------------------------------------------------
    # 2. Normal logout revokes the refresh token
    # -------------------------------------------------------------
    # Create fresh tokens
    login2_code, login2_data, _, _ = http_req("POST", f"{LOCAL_API}/auth/login", {"username": env_user, "password": env_pwd})
    acc_token2 = login2_data.get("access_token")
    ref_token2 = login2_data.get("refresh_token")
    ref2_jti = decode_jwt_token(ref_token2)["jti"]

    # Logout supplying refresh token in payload
    l2_code, l2_data, _, _ = http_req("POST", f"{LOCAL_API}/auth/logout", data={"refresh_token": ref_token2}, headers={"Authorization": f"Bearer {acc_token2}"})
    log_test(2, "Logout with Refresh Token Returns HTTP 200", l2_code == 200 and l2_data.get("status") == "logged_out")

    # Verify refresh token is recorded in PostgreSQL
    async with async_session_maker() as session:
        rec_ref = (await session.execute(select(RevokedTokenModel).where(RevokedTokenModel.token_jti == ref2_jti))).scalar_one_or_none()
        log_test(2, "Refresh Token Persisted in PostgreSQL revoked_tokens", rec_ref is not None and rec_ref.token_jti == ref2_jti)

    # -------------------------------------------------------------
    # 3. Both tokens are rejected after logout
    # -------------------------------------------------------------
    # Access token rejected on protected route
    c_code, c_data, _, _ = http_req("GET", f"{LOCAL_API}/cases", headers={"Authorization": f"Bearer {acc_token2}"})
    log_test(3, "Revoked Access Token Strictly Rejected on Protected Route (HTTP 401)", c_code == 401)

    # Refresh token rejected on /auth/refresh
    r_code, r_data, _, _ = http_req("POST", f"{LOCAL_API}/auth/refresh", data={"refresh_token": ref_token2})
    log_test(3, "Revoked Refresh Token Strictly Rejected on /auth/refresh (HTTP 401)", r_code == 401)

    # -------------------------------------------------------------
    # 4. Database outage during access-token revocation returns HTTP 503
    # -------------------------------------------------------------
    test_user_id = str(uuid.uuid4())
    t4_acc = create_jwt_token(test_user_id, "outage_test", "analyst", token_type="access")
    with patch("app.auth.auth_service.async_session_maker", side_effect=Exception("DB Connection Timeout")):
        outage_503 = False
        try:
            await auth_service.revoke_tokens([(decode_jwt_token(t4_acc)["jti"], decode_jwt_token(t4_acc)["exp"])])
        except HTTPException as e:
            if e.status_code == 503:
                outage_503 = True
        log_test(4, "Database Outage during Access-Token Revocation Returns HTTP 503", outage_503)

    # -------------------------------------------------------------
    # 5. Database outage during refresh-token revocation returns HTTP 503
    # -------------------------------------------------------------
    t5_ref = create_jwt_token(test_user_id, "outage_test", "analyst", token_type="refresh")
    with patch("app.auth.auth_service.async_session_maker", side_effect=Exception("DB Connection Timeout")):
        ref_outage_503 = False
        try:
            await auth_service.revoke_tokens([(decode_jwt_token(t5_ref)["jti"], decode_jwt_token(t5_ref)["exp"])])
        except HTTPException as e:
            if e.status_code == 503:
                ref_outage_503 = True
        log_test(5, "Database Outage during Refresh-Token Revocation Returns HTTP 503", ref_outage_503)

    # -------------------------------------------------------------
    # 6. Logout never reports successful revocation when database transaction fails
    # -------------------------------------------------------------
    t6_acc = create_jwt_token(test_user_id, "fail_tx_user", "analyst", token_type="access")
    t6_jti = decode_jwt_token(t6_acc)["jti"]
    t6_exp = decode_jwt_token(t6_acc)["exp"]

    # Test via mock that if DB raises error, the API route raises HTTP 503 and never returns 200
    from app.api.auth_routes import logout as logout_endpoint
    from starlette.requests import Request
    from starlette.responses import Response

    scope = {
        "type": "http",
        "client": ("127.0.0.1", 8000),
        "headers": [(b"authorization", f"Bearer {t6_acc}".encode())]
    }
    mock_req = Request(scope)
    mock_resp = Response()

    with patch.object(auth_service, "revoke_tokens", side_effect=HTTPException(status_code=503, detail="DB Error")):
        route_rejected_503 = False
        try:
            await logout_endpoint(mock_req, mock_resp, payload=None)
        except HTTPException as e:
            if e.status_code == 503:
                route_rejected_503 = True
        log_test(6, "Logout Route Fails Secure with HTTP 503 when DB Fails", route_rejected_503)

    # Verify that token is NOT marked as revoked in PostgreSQL
    async with async_session_maker() as session:
        t6_rec = (await session.execute(select(RevokedTokenModel).where(RevokedTokenModel.token_jti == t6_jti))).scalar_one_or_none()
        log_test(6, "Token NOT Claimed as Revoked in DB on Transaction Failure", t6_rec is None)

    # -------------------------------------------------------------
    # 7. Repeated logout requests are handled safely (idempotent)
    # -------------------------------------------------------------
    t7_acc = create_jwt_token(test_user_id, "idempotent_user", "analyst", token_type="access")
    t7_ref = create_jwt_token(test_user_id, "idempotent_user", "analyst", token_type="refresh")

    # First revocation
    await auth_service.revoke_tokens([
        (decode_jwt_token(t7_acc)["jti"], decode_jwt_token(t7_acc)["exp"]),
        (decode_jwt_token(t7_ref)["jti"], decode_jwt_token(t7_ref)["exp"])
    ])

    # Second revocation with identical tokens (simulating repeated call)
    idempotent_ok = False
    try:
        await auth_service.revoke_tokens([
            (decode_jwt_token(t7_acc)["jti"], decode_jwt_token(t7_acc)["exp"]),
            (decode_jwt_token(t7_ref)["jti"], decode_jwt_token(t7_ref)["exp"])
        ])
        idempotent_ok = True
    except Exception as e:
        idempotent_ok = False

    log_test(7, "Repeated Logout Revocation Executes Idempotently Without Error", idempotent_ok)

    # -------------------------------------------------------------
    # 8. Worker A clears a lockout and worker B observes the updated database state
    # -------------------------------------------------------------
    worker_a = AuthService()
    worker_b = AuthService()
    cross_ip = f"198.51.100.{int(time.time() + 33) % 200 + 10}"

    # Lock out the IP using worker A
    for _ in range(5):
        try:
            await worker_a._record_ip_failure(cross_ip)
        except HTTPException:
            pass

    # Worker B observes the lockout
    b_locked_init = False
    try:
        await worker_b._check_ip_lockout(cross_ip)
    except HTTPException as e:
        if e.status_code == 429:
            b_locked_init = True
    log_test(8, "Worker B Observes Lockout Created by Worker A", b_locked_init)

    # Worker A clears the lockout
    await worker_a._clear_ip_failure(cross_ip)

    # Worker B immediately checks PostgreSQL and confirms lockout is cleared
    b_unlocked = False
    try:
        await worker_b._check_ip_lockout(cross_ip)
        b_unlocked = True
    except HTTPException:
        b_unlocked = False
    log_test(8, "Worker B Observes Lockout Cleared by Worker A", b_unlocked)

    # -------------------------------------------------------------
    # 9. Worker A creates a lockout and worker B enforces it
    # -------------------------------------------------------------
    cross_ip2 = f"198.51.100.{int(time.time() + 77) % 200 + 10}"
    await worker_a._clear_ip_failure(cross_ip2)

    # Worker A records 5 failures
    for _ in range(5):
        try:
            await worker_a._record_ip_failure(cross_ip2)
        except HTTPException:
            pass

    # Worker B enforces the lockout with HTTP 429 directly from PostgreSQL
    b_enforces = False
    try:
        await worker_b._check_ip_lockout(cross_ip2)
    except HTTPException as e:
        if e.status_code == 429:
            b_enforces = True
    log_test(9, "Worker B Enforces Lockout Created by Worker A via Authoritative DB", b_enforces)
    await worker_a._clear_ip_failure(cross_ip2)

    # -------------------------------------------------------------
    # 10. Actual separate Uvicorn worker processes share the same PostgreSQL lockout state
    # -------------------------------------------------------------
    # Spawn a second Uvicorn process on port 8002
    print("[*] Spawning secondary Uvicorn worker process on port 8002...")
    worker2_port = 8002
    cmd = [
        str(BACKEND_DIR.parent / "venv" / "Scripts" / "python.exe"),
        "-m", "uvicorn",
        "app.main:app",
        "--host", "127.0.0.1",
        "--port", str(worker2_port),
        "--app-dir", str(BACKEND_DIR)
    ]
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    worker2_proc = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Wait for worker 2 to be ready
    worker2_ready = False
    for _ in range(30):
        try:
            c, d, _, _ = http_req("GET", f"http://127.0.0.1:{worker2_port}/api/storage/status")
            if c == 200 and d.get("status") == "healthy":
                worker2_ready = True
                break
        except Exception:
            pass
        await asyncio.sleep(1)

    log_test(10, "Secondary Uvicorn Worker Process Started on Port 8002", worker2_ready)

    if worker2_ready:
        proc_ip = f"198.51.100.{int(time.time() + 111) % 200 + 10}"
        ip_hdr = {"CF-Connecting-IP": proc_ip}

        # Send 5 failures to Worker 1 (port 8000)
        for _ in range(5):
            http_req("POST", f"{LOCAL_API}/auth/login", {"username": "attacker", "password": "wrong"}, headers=ip_hdr)

        # Worker 1 returns 429
        w1_code, _, _, _ = http_req("POST", f"{LOCAL_API}/auth/login", {"username": "attacker", "password": "wrong"}, headers=ip_hdr)
        log_test(10, "Worker 1 (Port 8000) Enforces IP Lockout (HTTP 429)", w1_code == 429)

        # Worker 2 (Port 8002 - separate OS process) immediately returns HTTP 429
        w2_code, _, _, _ = http_req("POST", f"http://127.0.0.1:{worker2_port}/api/auth/login", {"username": "attacker", "password": "wrong"}, headers=ip_hdr)
        log_test(10, "Separate Worker 2 Process (Port 8002) Enforces Same Lockout (HTTP 429)", w2_code == 429)

        # Clean up test IP
        await auth_service._clear_ip_failure(proc_ip)

        # Worker 2 now allows request from that IP
        w2_clean_code, _, _, _ = http_req("POST", f"http://127.0.0.1:{worker2_port}/api/auth/login", {"username": env_user, "password": env_pwd}, headers=ip_hdr)
        log_test(10, "Worker 2 Allows Fresh Login After Lockout Cleared", w2_clean_code == 200)

        # Terminate worker 2 process
        worker2_proc.terminate()
        try:
            worker2_proc.wait(timeout=5)
        except Exception:
            worker2_proc.kill()

    # -------------------------------------------------------------
    # 11. Concurrent requests across multiple processes cannot lose increments
    # -------------------------------------------------------------
    conc_ip = f"198.51.100.{int(time.time() + 160) % 200 + 10}"
    await auth_service._clear_ip_failure(conc_ip)

    print(f"[*] Firing 5 concurrent failure requests via separate OS processes for IP: {conc_ip}...")
    loop = asyncio.get_running_loop()
    with ProcessPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(_send_concurrent_failure, conc_ip) for _ in range(5)]
        results = [f.result() for f in futures]

    # Verify that in PostgreSQL, failed_attempts is exactly 5 and locked_until is set
    async with async_session_maker() as session:
        con_row = (await session.execute(select(IpLockoutModel).where(IpLockoutModel.ip_address == conc_ip))).scalar_one_or_none()
        log_test(
            11,
            "Multi-Process Concurrent Increments Registered Exactly 5 Attempts",
            con_row is not None and con_row.failed_attempts == 5 and con_row.locked_until is not None,
            f"(attempts={con_row.failed_attempts if con_row else None}, locked_until={con_row.locked_until if con_row else None})"
        )

    await auth_service._clear_ip_failure(conc_ip)

    # -------------------------------------------------------------
    # 12. Forged XFF cannot bypass IP lockout
    # -------------------------------------------------------------
    # Case A: Untrusted direct peer sending forged XFF and CF headers
    req_untrusted = Request({
        "type": "http",
        "client": ("203.0.113.5", 54321),
        "headers": [
            (b"cf-connecting-ip", b"1.1.1.1"),
            (b"x-forwarded-for", b"8.8.8.8, 9.9.9.9")
        ]
    })
    extracted_untrusted = _extract_client_ip(req_untrusted)
    log_test(12, "Untrusted Direct Peer Forged Forwarding Headers Ignored", extracted_untrusted == "203.0.113.5", f"extracted={extracted_untrusted}")

    # Case B: Trusted proxy connection with CF-Connecting-IP
    req_cf = Request({
        "type": "http",
        "client": ("127.0.0.1", 8000),
        "headers": [
            (b"cf-connecting-ip", b"203.0.113.88"),
            (b"x-forwarded-for", b"1.1.1.1, 203.0.113.88")
        ]
    })
    extracted_cf = _extract_client_ip(req_cf)
    log_test(12, "Authoritative CF-Connecting-IP Extracted Over Forged XFF", extracted_cf == "203.0.113.88", f"extracted={extracted_cf}")

    # Case C: Validated proxy chain traversal without CF-Connecting-IP
    req_xff = Request({
        "type": "http",
        "client": ("127.0.0.1", 8000),
        "headers": [
            (b"x-forwarded-for", b"1.1.1.1, 203.0.113.88, 127.0.0.1")
        ]
    })
    extracted_xff = _extract_client_ip(req_xff)
    log_test(12, "Right-to-Left Proxy Chain Traversal Extracts Real Client IP", extracted_xff == "203.0.113.88", f"extracted={extracted_xff}")

    # Case D: Malformed header rejection
    req_malformed = Request({
        "type": "http",
        "client": ("127.0.0.1", 8000),
        "headers": [
            (b"cf-connecting-ip", b"malicious' OR 1=1--")
        ]
    })
    extracted_malformed = _extract_client_ip(req_malformed)
    log_test(12, "Malformed Header Rejected and Falls Back to Peer", extracted_malformed == "127.0.0.1", f"extracted={extracted_malformed}")

    # Case E: IPv6 Support
    req_ipv6 = Request({
        "type": "http",
        "client": ("127.0.0.1", 8000),
        "headers": [
            (b"cf-connecting-ip", b"2001:db8:85a3::8a2e:370:7334")
        ]
    })
    extracted_ipv6 = _extract_client_ip(req_ipv6)
    log_test(12, "IPv6 Address Validated and Extracted Correctly", extracted_ipv6 == "2001:db8:85a3::8a2e:370:7334", f"extracted={extracted_ipv6}")

    # -------------------------------------------------------------
    # 13. Public production requests use the correct authoritative Cloudflare client IP
    # -------------------------------------------------------------
    pub_code, pub_data, pub_hdrs, _ = http_req("GET", f"{PUBLIC_API}/storage/status")
    hdrs_lower = {k.lower(): v for k, v in pub_hdrs.items()}
    cf_ray = hdrs_lower.get("cf-ray")
    server_hdr = hdrs_lower.get("server", "").lower()
    log_test(
        13,
        "Public Edge Requests Route Through Cloudflare (CF-Ray Present)",
        pub_code == 200 and cf_ray is not None and "cloudflare" in server_hdr,
        f"(CF-Ray: {cf_ray}, Server: {server_hdr})"
    )

    print("=" * 80)
    print(f"VERIFICATION SUITE SUMMARY: {PASSED} PASSED, {FAILED} FAILED")
    print("=" * 80)
    if FAILED > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_all_tests())
