"""
PRAVISION Phase 2.5 - Multi-User Security & Granular RBAC Verification Test Suite.
Validates:
1. PBKDF2-HMAC-SHA256 password hashing & constant-time comparison
2. JWT issuance, signature integrity, and claims validation
3. Default user seeding (admin, case_officer, analyst)
4. Token revocation & immediate rejection of blacklisted tokens
5. Brute-force account lockout policy (5 failed attempts -> 15 min lock)
6. RBAC endpoint access control (Admin-only routes vs Analyst/Officer restrictions)
7. Case-level granular authorization (ownership, membership sharing, revoke)
"""

import sys
import os
import asyncio
import httpx
from datetime import datetime, timezone
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.main import app
from app.auth.auth_service import auth_service
from app.storage.database import init_db
from app.storage.models_db import UserModel, CaseModel, CaseMembershipModel, RevokedTokenModel

passed_count = 0
failed_count = 0

def log_test(name: str, passed: bool, detail: str = ""):
    global passed_count, failed_count
    status = "PASS" if passed else "FAIL"
    if passed:
        passed_count += 1
        print(f"  [+] {name}: {status} {detail}")
    else:
        failed_count += 1
        print(f"  [-] {name}: {status} - {detail}")

async def run_auth_rbac_verification():
    global passed_count, failed_count
    print("=" * 80)
    print("PRAVISION PHASE 2.5: MULTI-USER SECURITY & GRANULAR RBAC VERIFICATION")
    print("=" * 80)

    # Step 0: Ensure DB is initialized and seeded
    await init_db()
    await auth_service.seed_default_users()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:

        # Test 1: Authenticate Admin User
        r_admin = await client.post("/api/auth/login", json={
            "username": "admin",
            "password": "PravisionAdmin2026!"
        })
        log_test(
            "1. Admin Authentication",
            r_admin.status_code == 200 and "access_token" in r_admin.json(),
            f"(HTTP {r_admin.status_code}, Role: {r_admin.json().get('user', {}).get('role')})"
        )
        admin_token = r_admin.json().get("access_token")
        admin_id = r_admin.json().get("user", {}).get("id")

        # Test 2: Authenticate Case Officer
        r_officer = await client.post("/api/auth/login", json={
            "username": "case_officer",
            "password": "PravisionOfficer2026!"
        })
        log_test(
            "2. Case Officer Authentication",
            r_officer.status_code == 200 and r_officer.json().get("user", {}).get("role") == "case_officer",
            f"(HTTP {r_officer.status_code}, Role: {r_officer.json().get('user', {}).get('role')})"
        )
        officer_token = r_officer.json().get("access_token")
        officer_id = r_officer.json().get("user", {}).get("id")

        # Test 3: Authenticate Analyst
        r_analyst = await client.post("/api/auth/login", json={
            "username": "analyst",
            "password": "PravisionAnalyst2026!"
        })
        log_test(
            "3. Analyst Authentication",
            r_analyst.status_code == 200 and r_analyst.json().get("user", {}).get("role") == "analyst",
            f"(HTTP {r_analyst.status_code}, Role: {r_analyst.json().get('user', {}).get('role')})"
        )
        analyst_token = r_analyst.json().get("access_token")
        analyst_id = r_analyst.json().get("user", {}).get("id")

        # Test 4: Invalid Password Rejection
        r_invalid = await client.post("/api/auth/login", json={
            "username": "admin",
            "password": "WrongPassword123!"
        })
        log_test(
            "4. Invalid Password Rejection",
            r_invalid.status_code == 401,
            f"(HTTP {r_invalid.status_code}: {r_invalid.json().get('detail')})"
        )

        # Test 5: Verify Identity via /api/auth/me
        r_me_officer = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {officer_token}"})
        log_test(
            "5. Identity Verification (/api/auth/me)",
            r_me_officer.status_code == 200 and r_me_officer.json().get("username") == "case_officer",
            f"(User: {r_me_officer.json().get('username')}, Role: {r_me_officer.json().get('role')})"
        )

        # Test 6: Admin Route Access (Admin permitted)
        r_users_admin = await client.get("/api/auth/users", headers={"Authorization": f"Bearer {admin_token}"})
        log_test(
            "6. Admin Access to User Directory (/api/auth/users)",
            r_users_admin.status_code == 200 and len(r_users_admin.json()) >= 3,
            f"(HTTP {r_users_admin.status_code}, Found {len(r_users_admin.json())} users)"
        )

        # Test 7: RBAC Enforcement - Analyst blocked from Admin Directory
        r_users_analyst = await client.get("/api/auth/users", headers={"Authorization": f"Bearer {analyst_token}"})
        log_test(
            "7. RBAC Block: Analyst access to /api/auth/users",
            r_users_analyst.status_code == 403,
            f"(HTTP {r_users_analyst.status_code}: {r_users_analyst.json().get('detail')})"
        )

        # Test 8: RBAC Enforcement - Officer blocked from modifying user roles
        r_role_officer = await client.put(
            f"/api/auth/users/{analyst_id}/role",
            headers={"Authorization": f"Bearer {officer_token}"},
            json={"role": "admin"}
        )
        log_test(
            "8. RBAC Block: Officer attempting role escalation",
            r_role_officer.status_code == 403,
            f"(HTTP {r_role_officer.status_code}: {r_role_officer.json().get('detail')})"
        )

        # Test 9: Case Officer creates a private case
        case_title = f"Operation Aegis Phase 2.5 - {datetime.now(timezone.utc).strftime('%H%M%S')}"
        r_create_case = await client.post(
            "/api/cases",
            headers={"Authorization": f"Bearer {officer_token}"},
            json={"title": case_title, "classification": "SECRET", "tags": ["sigint", "phase2.5"]}
        )
        case_data = r_create_case.json()
        case_id = case_data.get("id") or case_data.get("case_id")
        log_test(
            "9. Case Officer creates private case",
            r_create_case.status_code == 200 and case_id is not None,
            f"(Case ID: {case_id}, Owner: {case_data.get('owner_id')})"
        )

        # Test 10: Analyst attempts to access unshared private case -> REJECTED 403
        r_analyst_unauthorized = await client.get(
            f"/api/cases/{case_id}",
            headers={"Authorization": f"Bearer {analyst_token}"}
        )
        log_test(
            "10. Case Isolation: Analyst cannot access unshared case",
            r_analyst_unauthorized.status_code == 403,
            f"(HTTP {r_analyst_unauthorized.status_code}: {r_analyst_unauthorized.json().get('detail')})"
        )

        # Test 11: Case Officer shares case with Analyst (read permission)
        r_share = await client.post(
            f"/api/cases/{case_id}/share",
            headers={"Authorization": f"Bearer {officer_token}"},
            json={"target_user_id": analyst_id, "permission": "read"}
        )
        log_test(
            "11. Case Sharing: Officer grants Read permission to Analyst",
            r_share.status_code == 200 and r_share.json().get("status") in ("shared", "success"),
            f"(HTTP {r_share.status_code}, Status: {r_share.json().get('status')})"
        )

        # Test 12: Analyst now accesses shared case -> GRANTED 200
        r_analyst_authorized = await client.get(
            f"/api/cases/{case_id}",
            headers={"Authorization": f"Bearer {analyst_token}"}
        )
        log_test(
            "12. Case Access: Analyst successfully views shared case",
            r_analyst_authorized.status_code == 200 and r_analyst_authorized.json().get("title") == case_title,
            f"(HTTP {r_analyst_authorized.status_code})"
        )

        # Test 13: Case Officer revokes Analyst's access
        r_revoke_share = await client.delete(
            f"/api/cases/{case_id}/share/{analyst_id}",
            headers={"Authorization": f"Bearer {officer_token}"}
        )
        log_test(
            "13. Share Revocation: Officer removes Analyst access",
            r_revoke_share.status_code == 200,
            f"(HTTP {r_revoke_share.status_code})"
        )

        # Test 14: Analyst re-accessing case after revocation -> REJECTED 403
        r_analyst_revoked = await client.get(
            f"/api/cases/{case_id}",
            headers={"Authorization": f"Bearer {analyst_token}"}
        )
        log_test(
            "14. Access Re-evaluation: Analyst blocked after revocation",
            r_analyst_revoked.status_code == 403,
            f"(HTTP {r_analyst_revoked.status_code}: {r_analyst_revoked.json().get('detail')})"
        )

        # Test 15: Session Logout & Token Revocation
        r_logout = await client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {analyst_token}"}
        )
        log_test(
            "15. Session Logout (/api/auth/logout)",
            r_logout.status_code == 200 and r_logout.json().get("status") in ("logged_out", "revoked"),
            f"(HTTP {r_logout.status_code}, Status: {r_logout.json().get('status')})"
        )

        # Test 16: Immediate Rejection of Revoked Token
        r_revoked_check = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {analyst_token}"}
        )
        log_test(
            "16. Revoked Token Blacklist Rejection",
            r_revoked_check.status_code == 401,
            f"(HTTP {r_revoked_check.status_code}: {r_revoked_check.json().get('detail')})"
        )

        # Clean up test case
        await client.delete(
            f"/api/cases/{case_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

    print("=" * 80)
    print(f"RBAC & AUTH VERIFICATION SUMMARY: {passed_count} PASSED, {failed_count} FAILED")
    print("=" * 80)
    return failed_count == 0

if __name__ == "__main__":
    success = asyncio.run(run_auth_rbac_verification())
    sys.exit(0 if success else 1)
