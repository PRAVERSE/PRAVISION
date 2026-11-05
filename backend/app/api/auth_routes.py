import logging
import ipaddress
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status, Body

from app.storage.models_db import UserModel, CaseMembershipModel
from app.auth.auth_service import (
    auth_service,
    get_current_user,
    require_role,
    verify_case_access,
    decode_jwt_token,
    create_jwt_token
)
from app.storage.database import async_session_maker
from sqlalchemy import select, delete

logger = logging.getLogger("pravision.api.auth")
auth_router = APIRouter(prefix="/auth", tags=["Authentication & Access Control"])

TRUSTED_PROXIES = {"127.0.0.1", "::1", "localhost", "testclient"}

def _extract_client_ip(request: Request) -> str:
    """Extracts client IP with strict proxy trust validation.
    
    Security rules:
    - Untrusted direct peers cannot provide forwarded headers; return peer directly.
    - When connecting from a verified local proxy (TRUSTED_PROXIES):
      Only trust Cloudflare's authoritative 'CF-Connecting-IP' header, cryptographically
      tied to the edge connection.
    - The CF-Connecting-IP must be validated as a valid IPv4 or IPv6 address.
    - If CF-Connecting-IP is missing, empty, or malformed, arbitrary X-Forwarded-For
      headers are NEVER trusted; safely fall back to the direct peer IP.
    """
    peer = request.client.host if request.client and request.client.host else "127.0.0.1"
    
    # 1. Direct peer trust verification: untrusted peers cannot supply forwarded headers
    if peer not in TRUSTED_PROXIES:
        return peer

    # 2. Authoritative Cloudflare Edge header from trusted proxy
    cf_ip = request.headers.get("CF-Connecting-IP") or request.headers.get("cf-connecting-ip")
    if cf_ip:
        candidate = cf_ip.strip()
        try:
            parsed = ipaddress.ip_address(candidate)
            return str(parsed)
        except ValueError:
            logger.warning(f"Malformed CF-Connecting-IP header rejected: {cf_ip}")
            return peer

    # Untrusted/unverified XFF headers are discarded when CF-Connecting-IP is missing
    return peer

@auth_router.post("/login")
async def login(request: Request, response: Response, payload: Dict[str, Any] = Body(...)):
    raw_username = payload.get("username") if "username" in payload else (payload.get("user") if "user" in payload else payload.get("email"))
    raw_password = payload.get("password")
    
    if not isinstance(raw_username, str) or not raw_username.strip() or not isinstance(raw_password, str) or len(raw_password) == 0:
        raise HTTPException(status_code=400, detail="Username and password are required.")
    
    username = raw_username.strip()
    password = raw_password  # Strict exact string preservation (no trimming, lowercasing, or mutation)
    
    client_ip = _extract_client_ip(request)
    result = await auth_service.authenticate_user(username, password, ip_address=client_ip)
    
    # Set secure, HTTP-only session cookie
    response.set_cookie(
        key="pravision_session",
        value=result["access_token"],
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=8 * 3600,
        path="/"
    )
    return result

@auth_router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    payload: Optional[Dict[str, str]] = Body(None)
):
    """Invalidates active user sessions by revoking access and refresh tokens.
    
    Logout Failure Policy:
    - If any required server-side token revocation fails (e.g. database connection down),
      the endpoint strictly returns HTTP 503 ("Authentication service temporarily unavailable").
    - Cookies are NOT deleted on failure, allowing safe client retries.
    - Repeated/retried logout requests are idempotent: tokens already revoked do not cause
      duplicate key errors.
    - On successful commit of all server-side revocations, cookies are deleted and HTTP 200 is returned.
    """
    tokens_to_revoke = []
    user_id = None
    username = "unknown"

    # 1. Extract and decode access token (from Authorization header or session cookies)
    token = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif "pravision_session" in request.cookies:
        token = request.cookies.get("pravision_session")
    elif "pravision_token" in request.cookies:
        token = request.cookies.get("pravision_token")

    if token:
        try:
            p = decode_jwt_token(token)
            jti = p.get("jti")
            exp = p.get("exp", 0)
            user_id = p.get("sub")
            username = p.get("username", username)
            if jti and exp:
                tokens_to_revoke.append((jti, exp))
        except Exception as e:
            logger.warning(f"Failed to decode access token on logout: {e}")

    # 2. Extract and decode refresh token (from JSON body or cookies)
    refresh_token = (payload.get("refresh_token") if (payload and isinstance(payload, dict)) else None) or request.cookies.get("pravision_refresh_token")
    if refresh_token:
        try:
            rp = decode_jwt_token(refresh_token)
            rjti = rp.get("jti")
            rexp = rp.get("exp", 0)
            if not user_id:
                user_id = rp.get("sub")
                username = rp.get("username", username)
            if rjti and rexp:
                tokens_to_revoke.append((rjti, rexp))
        except Exception as e:
            logger.warning(f"Failed to decode refresh token on logout: {e}")

    # 3. Require at least one session token to proceed with logout
    if not tokens_to_revoke:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. No session or token provided for logout."
        )

    # 4. Commit server-side token revocations to PostgreSQL atomically.
    # If database fails, this raises HTTPException(status_code=503).
    # We do NOT swallow database errors; the client receives HTTP 503 and cookies remain intact for retry.
    await auth_service.revoke_tokens(tokens_to_revoke)

    # 5. Success Path: All server-side revocations committed to PostgreSQL.
    # Now instruct browser to delete session cookies.
    response.delete_cookie(key="pravision_session", path="/", httponly=True, secure=True, samesite="lax")
    response.delete_cookie(key="pravision_token", path="/", httponly=True, secure=True, samesite="lax")
    response.delete_cookie(key="pravision_refresh_token", path="/", httponly=True, secure=True, samesite="lax")

    client_ip = _extract_client_ip(request)
    if user_id:
        try:
            await auth_service.record_audit("user_logout", user_id, username, "auth", user_id, "success", {}, client_ip)
        except Exception:
            pass

    return {"status": "logged_out", "message": "Session invalidated successfully."}

@auth_router.get("/session")
async def check_session(request: Request):
    """Liveness check for active user session."""
    try:
        user = await get_current_user(request, None)
        return {
            "authenticated": True,
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "full_name": user.full_name
            }
        }
    except Exception:
        return {"authenticated": False, "user": None}

@auth_router.get("/me")
async def get_current_user_profile(current_user: UserModel = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role,
        "full_name": current_user.full_name,
        "is_active": current_user.is_active,
        "last_login": current_user.last_login.isoformat() if current_user.last_login else None
    }

@auth_router.post("/refresh")
async def refresh_access_token(payload: Dict[str, str] = Body(...)):
    refresh_token = payload.get("refresh_token", "").strip()
    if not refresh_token:
        raise HTTPException(status_code=400, detail="Refresh token required.")
    try:
        data = decode_jwt_token(refresh_token)
        if data.get("type") != "refresh":
            raise HTTPException(status_code=400, detail="Provided token is not a refresh token.")
        
        # Check revocation
        if await auth_service.is_token_revoked(data.get("jti")):
            raise HTTPException(status_code=401, detail="Refresh token has been revoked.")

        # Re-issue access token
        new_access = create_jwt_token(data["sub"], data["username"], data["role"], token_type="access")
        return {
            "access_token": new_access,
            "token_type": "bearer",
            "expires_in": 3600
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid refresh token: {e}")

# ----------------- ADMINISTRATIVE USER MANAGEMENT -----------------

@auth_router.get("/users")
async def list_all_users(admin_user: UserModel = Depends(require_role(["admin"]))):
    return await auth_service.list_users()

@auth_router.post("/users")
async def create_user_account(
    payload: Dict[str, Any] = Body(...),
    admin_user: UserModel = Depends(require_role(["admin"]))
):
    username = payload.get("username", "").strip()
    email = payload.get("email", "").strip()
    password = payload.get("password", "").strip()
    role = payload.get("role", "analyst")
    full_name = payload.get("full_name")

    if not username or not email or not password:
        raise HTTPException(status_code=400, detail="Username, email, and password are required.")
    try:
        return await auth_service.create_user(
            username=username,
            email=email,
            password=password,
            role=role,
            full_name=full_name,
            creator_user=admin_user.username
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@auth_router.put("/users/{user_id}/status")
async def update_user_status(
    user_id: str,
    payload: Dict[str, bool] = Body(...),
    admin_user: UserModel = Depends(require_role(["admin"]))
):
    is_active = payload.get("is_active", True)
    success = await auth_service.set_user_status(user_id, is_active, actor=admin_user.username)
    if not success:
        raise HTTPException(status_code=404, detail="User not found.")
    return {"status": "updated", "user_id": user_id, "is_active": is_active}

@auth_router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    payload: Dict[str, str] = Body(...),
    admin_user: UserModel = Depends(require_role(["admin"]))
):
    new_role = payload.get("role", "analyst")
    try:
        success = await auth_service.set_user_role(user_id, new_role, actor=admin_user.username)
        if not success:
            raise HTTPException(status_code=404, detail="User not found.")
        return {"status": "updated", "user_id": user_id, "role": new_role}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

