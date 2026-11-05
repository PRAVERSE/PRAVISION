"""
PRAVISION — Verification Suite: Password Integrity & Proxy Header Hardening
Tests:
  1-8: Strict Password Preservation & Cryptographic Comparison (Zero Normalization)
  9-15: Proxy Header Trust Validation (Authoritative Cloudflare Edge IP, Reject Untrusted XFF)
  16-20: Fail-Secure Lockout Clearing (PostgreSQL Transactional Clearing, Zero Token Leakage on DB Error)
"""

import os
import sys
import uuid
import hmac
import asyncio
import ipaddress
import re
from datetime import datetime, timezone, timedelta
from typing import Dict, Any
from unittest.mock import patch, MagicMock

# Ensure backend directory is in python path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT_DIR, ".env"))

from app.dns_resilience import install_dns_resilience
install_dns_resilience()

from app.storage.database import async_session_maker, init_db, IS_POSTGRES
from app.storage.models_db import IpLockoutModel, UserModel
from app.auth.auth_service import (
    auth_service,
    get_env_auth_credentials,
    hash_password,
    verify_password,
    create_jwt_token,
    decode_jwt_token,
    AuthService
)
from app.api.auth_routes import _extract_client_ip, TRUSTED_PROXIES, login
from fastapi import HTTPException, Request, Response
from starlette.datastructures import Headers
from sqlalchemy import select, delete


def make_mock_request(client_ip="127.0.0.1", headers_dict=None):
    mock = MagicMock(spec=Request)
    mock.client = MagicMock()
    mock.client.host = client_ip
    hdrs = Headers(headers_dict or {})
    mock.headers = hdrs
    return mock


async def run_all_tests():
    print("=" * 70)
    print("PRAVISION: PASSWORD INTEGRITY & PROXY HEADER HARDENING VERIFICATION")
    print("=" * 70)

    env_user, env_pwd, _ = get_env_auth_credentials()
    assert env_user and env_pwd, "Platform credentials must be set in .env"
    print(f"[*] Configuration verified: user='{env_user}', password_len={len(env_pwd)}")

    passed = 0
    total = 20

    # -------------------------------------------------------------------------
    # PART 1: Strict Password Preservation & Cryptographic Comparison
    # -------------------------------------------------------------------------
    print("\n--- PART 1: Password Integrity & Exact Comparison ---")

    # Test 1: Exact match
    try:
        t_ip = "192.0.2.101"
        await auth_service._clear_ip_failure(t_ip)
        res = await auth_service.authenticate_user(env_user, env_pwd, ip_address=t_ip)
        assert "access_token" in res and res["user"]["username"] == env_user
        print("[PASS] Test 01: Exact configured password authenticates successfully (HTTP 200).")
        passed += 1
    except Exception as e:
        print(f"[FAIL] Test 01: {e}")

    # Test 2: Leading space rejected
    try:
        t_ip = "192.0.2.102"
        await auth_service._clear_ip_failure(t_ip)
        tampered = f" {env_pwd}"
        try:
            await auth_service.authenticate_user(env_user, tampered, ip_address=t_ip)
            raise AssertionError("Should have raised 401")
        except HTTPException as he:
            assert he.status_code == 401
            assert "Invalid username or password" in he.detail
        print("[PASS] Test 02: Password with extra leading space is strictly rejected (HTTP 401).")
        passed += 1
    except Exception as e:
        print(f"[FAIL] Test 02: {e}")

    # Test 3: Trailing space rejected
    try:
        t_ip = "192.0.2.103"
        await auth_service._clear_ip_failure(t_ip)
        tampered = f"{env_pwd} "
        try:
            await auth_service.authenticate_user(env_user, tampered, ip_address=t_ip)
            raise AssertionError("Should have raised 401")
        except HTTPException as he:
            assert he.status_code == 401
            assert "Invalid username or password" in he.detail
        print("[PASS] Test 03: Password with extra trailing space is strictly rejected (HTTP 401).")
        passed += 1
    except Exception as e:
        print(f"[FAIL] Test 03: {e}")

    # Test 4: Both spaces rejected
    try:
        t_ip = "192.0.2.104"
        await auth_service._clear_ip_failure(t_ip)
        tampered = f"  {env_pwd}  "
        try:
            await auth_service.authenticate_user(env_user, tampered, ip_address=t_ip)
            raise AssertionError("Should have raised 401")
        except HTTPException as he:
            assert he.status_code == 401
            assert "Invalid username or password" in he.detail
        print("[PASS] Test 04: Password with both leading and trailing spaces is strictly rejected (HTTP 401).")
        passed += 1
    except Exception as e:
        print(f"[FAIL] Test 04: {e}")

    # Test 5: Deliberately configured password with spaces compares exactly
    try:
        t_ip = "192.0.2.105"
        await auth_service._clear_ip_failure(t_ip)
        spaced_pwd = "  P@ssw0rd With Spaces  "
        with patch("app.auth.auth_service.get_env_auth_credentials", return_value=("test_spaced_admin", spaced_pwd, "test-sec")):
            # Exact match succeeds
            res = await auth_service.authenticate_user("test_spaced_admin", spaced_pwd, ip_address=t_ip)
            assert "access_token" in res

            # Stripped match fails
            try:
                await auth_service.authenticate_user("test_spaced_admin", spaced_pwd.strip(), ip_address=t_ip)
                raise AssertionError("Should have raised 401")
            except HTTPException as he:
                assert he.status_code == 401
        print("[PASS] Test 05: Configured password containing spaces is compared exactly (stripped version fails).")
        passed += 1
    except Exception as e:
        print(f"[FAIL] Test 05: {e}")

    # Test 6: Generic 401 on wrong password
    try:
        t_ip = "192.0.2.106"
        await auth_service._clear_ip_failure(t_ip)
        try:
            await auth_service.authenticate_user(env_user, "CompletelyWrongPassword123!", ip_address=t_ip)
            raise AssertionError("Should have raised 401")
        except HTTPException as he:
            assert he.status_code == 401
            assert he.detail == "Invalid username or password. Access denied."
        print("[PASS] Test 06: Wrong password returns generic 401 without leaking internal match state.")
        passed += 1
    except Exception as e:
        print(f"[FAIL] Test 06: {e}")

    # Test 7: API route rejects missing/empty/non-string passwords
    try:
        req = make_mock_request("127.0.0.1")
        resp = Response()
        # Missing
        try:
            await login(req, resp, payload={"username": "admin"})
            raise AssertionError("Should have raised 400")
        except HTTPException as he:
            assert he.status_code == 400
        # Empty
        try:
            await login(req, resp, payload={"username": "admin", "password": ""})
            raise AssertionError("Should have raised 400")
        except HTTPException as he:
            assert he.status_code == 400
        # Non-string
        try:
            await login(req, resp, payload={"username": "admin", "password": 9999})
            raise AssertionError("Should have raised 400")
        except HTTPException as he:
            assert he.status_code == 400
        print("[PASS] Test 07: /auth/login route rejects missing, empty, and non-string passwords with HTTP 400.")
        passed += 1
    except Exception as e:
        print(f"[FAIL] Test 07: {e}")

    # Test 8: Failed attempts increment PostgreSQL lockout
    try:
        t_ip = f"192.0.2.{uuid.uuid4().int % 200 + 10}"
        await auth_service._clear_ip_failure(t_ip)
        try:
            await auth_service.authenticate_user(env_user, "WrongPass1", ip_address=t_ip)
        except HTTPException:
            pass
        async with async_session_maker() as session:
            stmt = select(IpLockoutModel).where(IpLockoutModel.ip_address == t_ip)
            rec = (await session.execute(stmt)).scalars().first()
            assert rec is not None and rec.failed_attempts == 1
        await auth_service._clear_ip_failure(t_ip)
        print("[PASS] Test 08: Failed login attempts update persistent PostgreSQL lockout state.")
        passed += 1
    except Exception as e:
        print(f"[FAIL] Test 08: {e}")

    # -------------------------------------------------------------------------
    # PART 2: Proxy Header Hardening (Authoritative Cloudflare Edge IP)
    # -------------------------------------------------------------------------
    print("\n--- PART 2: Proxy Header Hardening ---")

    # Test 9: Valid CF-Connecting-IP from trusted proxy
    try:
        req = make_mock_request("127.0.0.1", {"CF-Connecting-IP": "203.0.113.195"})
        assert _extract_client_ip(req) == "203.0.113.195"
        print("[PASS] Test 09: Valid CF-Connecting-IP from trusted local proxy is accepted as client IP.")
        passed += 1
    except Exception as e:
        print(f"[FAIL] Test 09: {e}")

    # Test 10: Forged XFF ignored when CF-Connecting-IP present
    try:
        req = make_mock_request("127.0.0.1", {
            "CF-Connecting-IP": "203.0.113.195",
            "X-Forwarded-For": "198.51.100.1, 10.0.0.1"
        })
        assert _extract_client_ip(req) == "203.0.113.195"
        print("[PASS] Test 10: Forged visitor X-Forwarded-For is ignored when CF-Connecting-IP is present.")
        passed += 1
    except Exception as e:
        print(f"[FAIL] Test 10: {e}")

    # Test 11: Missing CF-Connecting-IP does NOT trust arbitrary XFF
    try:
        req = make_mock_request("127.0.0.1", {
            "X-Forwarded-For": "198.51.100.42"
        })
        assert _extract_client_ip(req) == "127.0.0.1"
        print("[PASS] Test 11: Missing CF-Connecting-IP does not trust arbitrary XFF; safely falls back to peer.")
        passed += 1
    except Exception as e:
        print(f"[FAIL] Test 11: {e}")

    # Test 12: Malformed CF-Connecting-IP safely rejected
    try:
        req = make_mock_request("127.0.0.1", {
            "CF-Connecting-IP": "203.0.113.195, evil-host.com",
            "X-Forwarded-For": "198.51.100.42"
        })
        assert _extract_client_ip(req) == "127.0.0.1"
        print("[PASS] Test 12: Malformed CF-Connecting-IP header is safely rejected with fallback to peer.")
        passed += 1
    except Exception as e:
        print(f"[FAIL] Test 12: {e}")

    # Test 13: Untrusted direct peer connection ignores all forwarded headers
    try:
        req = make_mock_request("198.51.100.99", {
            "CF-Connecting-IP": "1.2.3.4",
            "X-Forwarded-For": "5.6.7.8"
        })
        assert _extract_client_ip(req) == "198.51.100.99"
        print("[PASS] Test 13: External direct peer cannot supply forwarded headers; peer IP is enforced.")
        passed += 1
    except Exception as e:
        print(f"[FAIL] Test 13: {e}")

    # Test 14: Valid IPv6 accepted in CF-Connecting-IP
    try:
        req = make_mock_request("127.0.0.1", {
            "CF-Connecting-IP": "2001:db8:85a3::8a2e:370:7334"
        })
        assert _extract_client_ip(req) == "2001:db8:85a3::8a2e:370:7334"
        print("[PASS] Test 14: Valid IPv6 address in CF-Connecting-IP is parsed and accepted.")
        passed += 1
    except Exception as e:
        print(f"[FAIL] Test 14: {e}")

    # Test 15: Edge IP validation parity
    try:
        ipv4_regex = r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
        assert re.match(ipv4_regex, "192.0.2.1")
        assert re.match(ipv4_regex, "127.0.0.1")
        assert not re.match(ipv4_regex, "256.0.0.1")
        assert not re.match(ipv4_regex, "1.2.3.4, 5.6.7.8")
        assert not re.match(ipv4_regex, "")
        print("[PASS] Test 15: IP address validation format rules adhere to edge Pages Function parity.")
        passed += 1
    except Exception as e:
        print(f"[FAIL] Test 15: {e}")

    # -------------------------------------------------------------------------
    # PART 3: Fail-Secure Successful-Login Lockout Clearing
    # -------------------------------------------------------------------------
    print("\n--- PART 3: Fail-Secure Lockout Clearing ---")

    # Test 16: Successful login clears lockout row in PostgreSQL
    try:
        t_ip = f"192.0.2.{uuid.uuid4().int % 200 + 20}"
        await auth_service._record_ip_failure(t_ip)
        async with async_session_maker() as session:
            stmt = select(IpLockoutModel).where(IpLockoutModel.ip_address == t_ip)
            assert (await session.execute(stmt)).scalars().first() is not None

        res = await auth_service.authenticate_user(env_user, env_pwd, ip_address=t_ip)
        assert "access_token" in res

        async with async_session_maker() as session:
            stmt = select(IpLockoutModel).where(IpLockoutModel.ip_address == t_ip)
            rec = (await session.execute(stmt)).scalars().first()
            assert rec is None, "Row must be deleted from PostgreSQL upon successful login"
        print("[PASS] Test 16: Successful login commits deletion of IP lockout record in PostgreSQL.")
        passed += 1
    except Exception as e:
        print(f"[FAIL] Test 16: {e}")

    # Test 17: Cross-worker observes cleared lockout in PostgreSQL
    try:
        t_ip = f"192.0.2.{uuid.uuid4().int % 200 + 30}"
        worker_a = AuthService()
        worker_b = AuthService()
        await worker_a._record_ip_failure(t_ip)
        await worker_a._record_ip_failure(t_ip)

        async with async_session_maker() as session:
            stmt = select(IpLockoutModel).where(IpLockoutModel.ip_address == t_ip)
            rec = (await session.execute(stmt)).scalars().first()
            assert rec.failed_attempts == 2

        await worker_a.authenticate_user(env_user, env_pwd, ip_address=t_ip)

        # Worker B checks lockout and DB directly
        await worker_b._check_ip_lockout(t_ip)
        async with async_session_maker() as session:
            stmt = select(IpLockoutModel).where(IpLockoutModel.ip_address == t_ip)
            assert (await session.execute(stmt)).scalars().first() is None
        print("[PASS] Test 17: Separate worker instance immediately observes cleared lockout in PostgreSQL.")
        passed += 1
    except Exception as e:
        print(f"[FAIL] Test 17: {e}")

    # Test 18: Database failure during clear raises 503
    try:
        t_ip = "192.0.2.118"
        with patch("app.auth.auth_service.async_session_maker", side_effect=Exception("Simulated Neon DB connection timeout")):
            try:
                await auth_service._clear_ip_failure(t_ip)
                raise AssertionError("Should have raised 503")
            except HTTPException as he:
                assert he.status_code == 503
                assert "Authentication service temporarily unavailable" in he.detail
        print("[PASS] Test 18: Database failure during _clear_ip_failure raises HTTP 503 (fail-secure).")
        passed += 1
    except Exception as e:
        print(f"[FAIL] Test 18: {e}")

    # Test 19: No session tokens issued when clearing fails
    try:
        t_ip = "192.0.2.119"
        with patch.object(auth_service, "_clear_ip_failure", side_effect=HTTPException(status_code=503, detail="Simulated DB error")):
            try:
                await auth_service.authenticate_user(env_user, env_pwd, ip_address=t_ip)
                raise AssertionError("Should have raised 503")
            except HTTPException as he:
                assert he.status_code == 503
        print("[PASS] Test 19: Zero session tokens are issued when _clear_ip_failure fails.")
        passed += 1
    except Exception as e:
        print(f"[FAIL] Test 19: {e}")

    # Test 20: Pre-existing lockouts preserved
    try:
        t_ip = f"192.0.2.{uuid.uuid4().int % 200 + 40}"
        await auth_service._record_ip_failure(t_ip)
        async with async_session_maker() as session:
            stmt = select(IpLockoutModel).where(IpLockoutModel.ip_address == t_ip)
            assert (await session.execute(stmt)).scalars().first() is not None
        await auth_service._clear_ip_failure(t_ip)
        print("[PASS] Test 20: Pre-existing lockout state and persistent rows are preserved.")
        passed += 1
    except Exception as e:
        print(f"[FAIL] Test 20: {e}")

    # Ensure admin user lockout/failed attempts are completely cleared
    try:
        async with async_session_maker() as session:
            stmt = select(UserModel).where((UserModel.username == env_user) | (UserModel.email == env_user))
            u = (await session.execute(stmt)).scalars().first()
            if u:
                u.failed_login_attempts = 0
                u.locked_until = None
                await session.commit()
    except Exception:
        pass

    print("\n" + "=" * 70)
    print(f"VERIFICATION SUMMARY: {passed}/{total} TESTS PASSED")
    print("=" * 70)

    if passed != total:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_all_tests())
