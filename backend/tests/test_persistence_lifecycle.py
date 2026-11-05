"""
PRAVISION — Persistent Token Revocation & Rate-Limiting Lifecycle Test
Tests:
1. Token revocation persistence:
   - Create and revoke a token in Neon PostgreSQL
   - Verify is_token_revoked() returns True
   - Verify cleanup_expired_revoked_tokens() retains active revocations and removes expired ones
2. Persistent IP lockout & rate limiting:
   - Record 5 failed attempts for a test IP
   - Verify IP is locked out in PostgreSQL (IpLockoutModel)
   - Verify _check_ip_lockout raises HTTP 429
   - Clear IP failure and verify lockout is removed in PostgreSQL
"""

import sys
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.storage.database import init_db, async_session_maker
from app.storage.models_db import RevokedTokenModel, IpLockoutModel
from app.auth.auth_service import auth_service, create_jwt_token, decode_jwt_token
from fastapi import HTTPException
from sqlalchemy import select, delete

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

async def run_lifecycle_tests():
    print("=" * 70)
    print("TESTING PERSISTENT TOKEN REVOCATION & RATE LIMITING LIFECYCLE")
    print("=" * 70)

    await init_db()

    # 1. Persistent Token Revocation
    test_jti_active = "test-jti-active-persistence-12345"
    test_jti_expired = "test-jti-expired-persistence-67890"

    # Clean up test tokens if left over
    async with async_session_maker() as session:
        await session.execute(
            delete(RevokedTokenModel).where(
                RevokedTokenModel.token_jti.in_([test_jti_active, test_jti_expired])
            )
        )
        await session.commit()

    # Insert an active revocation (expires in 1 hour)
    active_exp = int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())
    await auth_service.revoke_token(test_jti_active, active_exp)

    # Insert an expired revocation directly (expired 1 hour ago)
    async with async_session_maker() as session:
        expired_rev = RevokedTokenModel(
            token_jti=test_jti_expired,
            expires_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
        )
        session.add(expired_rev)
        await session.commit()

    # Verify both are initially present
    active_revoked = await auth_service.is_token_revoked(test_jti_active)
    expired_revoked = await auth_service.is_token_revoked(test_jti_expired)
    check("Active Token Revocation Recorded in PostgreSQL", active_revoked is True)
    check("Expired Token Found Prior to Cleanup", expired_revoked is True)

    # Run cleanup of expired revocations
    purged = await auth_service.cleanup_expired_revoked_tokens()
    check("Cleanup Purged Expired Tokens", purged >= 1, f"Purged {purged} records")

    # Verify active revocation survives, expired is gone
    active_after = await auth_service.is_token_revoked(test_jti_active)
    expired_after = await auth_service.is_token_revoked(test_jti_expired)
    check("Active Token Revocation Survives Cleanup in PostgreSQL", active_after is True)
    check("Expired Token Revocation Was Removed", expired_after is False)

    # Clean up active test token
    async with async_session_maker() as session:
        await session.execute(
            delete(RevokedTokenModel).where(RevokedTokenModel.token_jti == test_jti_active)
        )
        await session.commit()

    # 2. Persistent IP Rate-Limiting & Lockout
    test_ip = "192.0.2.199"  # RFC 5737 TEST-NET-2

    # Clear any previous test state
    await auth_service._clear_ip_failure(test_ip)

    # Verify no lockout initially
    try:
        await auth_service._check_ip_lockout(test_ip)
        check("Initial IP Check: No Lockout", True)
    except HTTPException:
        check("Initial IP Check: No Lockout", False, "Unexpected HTTPException")

    # Record 4 failures (less than threshold of 5)
    for i in range(4):
        await auth_service._record_ip_failure(test_ip)

    # Check not locked yet
    try:
        await auth_service._check_ip_lockout(test_ip)
        check("Pre-Threshold Check (4 failures): No Lockout", True)
    except HTTPException:
        check("Pre-Threshold Check (4 failures): No Lockout", False, "Premature lockout")

    # 5th failure triggers lockout
    try:
        await auth_service._record_ip_failure(test_ip)
    except HTTPException:
        pass

    # Verify database record in PostgreSQL
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    async with async_session_maker() as session:
        stmt = select(IpLockoutModel).where(IpLockoutModel.ip_address == test_ip)
        rec = (await session.execute(stmt)).scalar_one_or_none()
        check("PostgreSQL IpLockoutModel Row Created", rec is not None and rec.failed_attempts == 5)
        check("PostgreSQL locked_until Populated", rec is not None and rec.locked_until is not None and rec.locked_until > now_utc)

    # Verify _check_ip_lockout raises HTTP 429
    raised_429 = False
    try:
        await auth_service._check_ip_lockout(test_ip)
    except HTTPException as e:
        if e.status_code == 429:
            raised_429 = True
    check("IP Lockout Enforced with HTTP 429", raised_429)

    # Test restart simulation: clear in-memory cache, check if DB state enforces 429!
    auth_service._ip_lockout_cache.clear()
    check("In-Memory State Cleared (Simulating Process Restart)", len(auth_service._ip_lockout_cache) == 0)

    raised_429_post_restart = False
    try:
        await auth_service._check_ip_lockout(test_ip)
    except HTTPException as e:
        if e.status_code == 429:
            raised_429_post_restart = True
    check("IP Lockout Survives Restart from PostgreSQL", raised_429_post_restart)

    # Clear lockout and verify clean removal
    await auth_service._clear_ip_failure(test_ip)
    async with async_session_maker() as session:
        stmt = select(IpLockoutModel).where(IpLockoutModel.ip_address == test_ip)
        cleared_rec = (await session.execute(stmt)).scalar_one_or_none()
        check("IP Lockout Record Cleared from PostgreSQL", cleared_rec is None)

    print("=" * 70)
    print(f"PERSISTENCE TEST RESULTS: {PASSED} PASSED, {FAILED} FAILED")
    print("=" * 70)
    if FAILED > 0:
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(run_lifecycle_tests())
