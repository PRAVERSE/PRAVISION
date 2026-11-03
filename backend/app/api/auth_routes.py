import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status, Body

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

@auth_router.post("/login")
async def login(request: Request, payload: Dict[str, str] = Body(...)):
    username = payload.get("username", "").strip()
    password = payload.get("password", "").strip()
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password are required.")
    
    client_ip = request.client.host if request.client else "127.0.0.1"
    return await auth_service.authenticate_user(username, password, ip_address=client_ip)

@auth_router.post("/logout")
async def logout(request: Request, current_user: UserModel = Depends(get_current_user)):
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            payload = decode_jwt_token(token)
            jti = payload.get("jti")
            exp = payload.get("exp", 0)
            if jti:
                await auth_service.revoke_token(jti, exp)
        except Exception:
            pass
    client_ip = request.client.host if request.client else "127.0.0.1"
    await auth_service.record_audit("user_logout", current_user.id, current_user.username, "auth", current_user.id, "success", {}, client_ip)
    return {"status": "logged_out", "message": "Session invalidated successfully."}

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

