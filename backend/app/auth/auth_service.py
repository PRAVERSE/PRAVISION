# pyright: reportAttributeAccessIssue=false, reportGeneralTypeIssues=false, reportArgumentType=false, reportPossiblyUnboundVariable=false, reportOperatorIssue=false
import os
import sys
import json
import uuid
import hmac
import base64
import hashlib
import secrets
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path

from fastapi import Depends, HTTPException, Security, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select, update, text
from sqlalchemy.orm import selectinload

from app.config import WORKSPACE_DIR
from app.storage.database import async_session_maker
from app.storage.models_db import UserModel, CaseModel, CaseMembershipModel, RevokedTokenModel, AuditLogModel

logger = logging.getLogger("pravision.auth")

SECRET_KEY_FILE = WORKSPACE_DIR / "backend" / ".auth_secret"
ADMIN_CREDS_FILE = WORKSPACE_DIR / "backend" / ".initial_admin_credentials"

ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_DAYS = 7
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15

security_bearer = HTTPBearer(auto_error=False)

def get_or_create_jwt_secret() -> bytes:
    """Retrieve or generate persistent 256-bit HMAC secret."""
    env_secret = os.environ.get("PRAVISION_JWT_SECRET")
    if env_secret:
        return env_secret.encode("utf-8")
    if SECRET_KEY_FILE.exists():
        try:
            return bytes.fromhex(SECRET_KEY_FILE.read_text(encoding="utf-8").strip())
        except Exception:
            pass
    new_secret = os.urandom(32)
    SECRET_KEY_FILE.write_text(new_secret.hex(), encoding="utf-8")
    try:
        os.chmod(SECRET_KEY_FILE, 0o600)
    except Exception:
        pass
    return new_secret

JWT_SECRET = get_or_create_jwt_secret()

def hash_password(password: str) -> str:
    """Hash password using PBKDF2-HMAC-SHA256 with 600,000 rounds and random salt."""
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 600000)
    return f"pbkdf2_sha256$600000${salt.hex()}${dk.hex()}"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against stored PBKDF2 hash using constant-time comparison."""
    try:
        parts = hashed_password.split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
            return False
        iterations = int(parts[1])
        salt = bytes.fromhex(parts[2])
        expected_dk = bytes.fromhex(parts[3])
        actual_dk = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(actual_dk, expected_dk)
    except Exception:
        return False

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

def _b64url_decode(s: str) -> bytes:
    padding = 4 - (len(s) % 4)
    if padding and padding < 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s.encode("ascii"))

def create_jwt_token(
    user_id: str,
    username: str,
    role: str,
    token_type: str = "access",
    expires_delta: Optional[timedelta] = None
) -> str:
    """Generates an RFC-7519 compliant HMAC-SHA256 JWT token."""
    header = {"alg": "HS256", "typ": "JWT"}
    now = datetime.utcnow()
    exp = now + (expires_delta or (timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES) if token_type == "access" else timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)))
    
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "type": token_type,
        "jti": str(uuid.uuid4()),
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp())
    }

    h_enc = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    p_enc = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{h_enc}.{p_enc}".encode("ascii")
    sig = hmac.new(JWT_SECRET, signing_input, hashlib.sha256).digest()
    sig_enc = _b64url_encode(sig)
    return f"{h_enc}.{p_enc}.{sig_enc}"

def decode_jwt_token(token: str) -> Dict[str, Any]:
    """Validates signature, format, and expiry of a JWT token."""
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid JWT format.")
    h_enc, p_enc, sig_enc = parts
    signing_input = f"{h_enc}.{p_enc}".encode("ascii")
    expected_sig = hmac.new(JWT_SECRET, signing_input, hashlib.sha256).digest()
    actual_sig = _b64url_decode(sig_enc)
    if not hmac.compare_digest(actual_sig, expected_sig):
        raise ValueError("JWT signature verification failed.")
    payload = json.loads(_b64url_decode(p_enc).decode("utf-8"))
    if datetime.utcnow().timestamp() > payload.get("exp", 0):
        raise ValueError("Token has expired.")
    return payload

DISALLOWED_DEFAULT_PASSWORDS = {
    "pravisionadmin2026!",
    "pravisionofficer2026!",
    "pravisionanalyst2026!",
    "changethisadminpassword2026!",
    "changethisofficerpassword2026!",
    "changethisanalystpassword2026!",
    "admin",
    "password",
    "administrator",
    "admin123",
    "12345678",
    "root",
}

def validate_and_sanitize_initial_password(raw_pwd: Optional[str], role_name: str) -> str:
    """Strictly validates initial bootstrap credentials, rejecting known defaults or weak passwords."""
    is_prod = os.environ.get("ENVIRONMENT", "").lower() == "production" or os.environ.get("PRAVISION_ENV", "").lower() == "production"
    
    if not raw_pwd or not raw_pwd.strip():
        if is_prod:
            raise ValueError(
                f"Production security failure: {role_name.upper()}_INITIAL_PASSWORD is required in production. "
                "You must set a unique, complex password with minimum 12 characters."
            )
        # Generate cryptographically strong random password for non-production environments
        generated = secrets.token_urlsafe(16)
        logger.warning(f"No {role_name.upper()}_INITIAL_PASSWORD supplied. Generated secure random credential.")
        return generated

    clean_pwd = raw_pwd.strip()
    if clean_pwd.lower() in DISALLOWED_DEFAULT_PASSWORDS:
        raise ValueError(
            f"Security failure: {role_name.upper()}_INITIAL_PASSWORD uses a prohibited known default password ({clean_pwd}). "
            "You must supply a strong, custom password."
        )
    if len(clean_pwd) < 12:
        raise ValueError(
            f"Security failure: {role_name.upper()}_INITIAL_PASSWORD must be at least 12 characters (received {len(clean_pwd)})."
        )
    return clean_pwd

def get_env_auth_credentials() -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Retrieve auth credentials dynamically from .env or environment variables.
    
    Priority order:
    1. Explicit PRAVISION_* environment variables (e.g. PRAVISION_AUTH_USERNAME, PRAVISION_AUTH_PASSWORD)
    2. Explicit PRAVISION_* keys from .env file
    3. Project .env keys ('username', 'password', 'USER_NAME', etc.)
    4. Generic environment variables ONLY IF not on Windows and not conflicting with system accounts.
    """
    from dotenv import dotenv_values
    from app.config import WORKSPACE_DIR
    
    env_paths = [
        WORKSPACE_DIR / ".env",
        Path.cwd() / ".env",
        Path(__file__).resolve().parent.parent.parent / ".env",
    ]
    env_vals: Dict[str, str] = {}
    for p in env_paths:
        if p.exists():
            try:
                loaded = dotenv_values(p)
                if loaded:
                    env_vals.update({k: str(v) for k, v in loaded.items() if v is not None})
            except Exception:
                pass

    # Username lookup: Namespaced env var > Namespaced .env key > .env 'username' key (MUST PREVENT OS 'USERNAME' from overriding!)
    username = (
        os.environ.get("PRAVISION_AUTH_USERNAME") or
        env_vals.get("PRAVISION_AUTH_USERNAME") or
        env_vals.get("username") or
        env_vals.get("USER_NAME") or
        env_vals.get("USERNAME") or
        os.environ.get("PRAVISION_USER")
    )
    # Only fall back to os.environ.get("username") if not Windows and no .env file
    if not username and sys.platform != "win32":
        username = os.environ.get("username")

    # Password lookup: Namespaced env var > Namespaced .env key > .env 'password' key
    password = (
        os.environ.get("PRAVISION_AUTH_PASSWORD") or
        env_vals.get("PRAVISION_AUTH_PASSWORD") or
        env_vals.get("password") or
        env_vals.get("PASSWORD") or
        os.environ.get("PRAVISION_PASSWORD") or
        os.environ.get("password")
    )

    # Session / JWT Secret lookup
    secret = (
        os.environ.get("PRAVISION_SESSION_SECRET") or
        env_vals.get("PRAVISION_SESSION_SECRET") or
        os.environ.get("PRAVISION_JWT_SECRET") or
        env_vals.get("PRAVISION_JWT_SECRET") or
        os.environ.get("JWT_SECRET") or
        env_vals.get("JWT_SECRET")
    )

    clean_user = username.strip() if username else None
    clean_pwd = password if password is not None else None
    clean_sec = secret.strip() if secret else None

    correlation_id = uuid.uuid4().hex[:8]
    logger.info(
        f"[AUTH-{correlation_id}] Loaded auth credentials configuration: "
        f"username_configured={bool(clean_user)}, "
        f"password_configured={bool(clean_pwd)}, "
        f"secret_configured={bool(clean_sec)}"
    )

    return (clean_user, clean_pwd, clean_sec)

def get_deterministic_username_aliases(configured_identity: str) -> set[str]:
    """
    Computes the explicit, deterministic set of valid username representations for a configured identity.
    Strictly prevents cross-domain or wildcard prefix collisions:
    - If configured is 'user@domain.com':
        Accepted identities: strictly 'user@domain.com' and the bare local part 'user' (case-insensitive).
        Any input containing a DIFFERENT domain (e.g. 'user@other.org') is strictly rejected.
    - If configured is 'admin':
        Accepted identity: strictly 'admin' (case-insensitive).
    """
    clean = configured_identity.strip()
    norm = clean.lower()
    aliases = {clean, norm}
    if "@" in clean:
        local_part = clean.split("@", 1)[0].strip()
        if local_part:
            aliases.add(local_part)
            aliases.add(local_part.lower())
    return aliases

class AuthService:
    """Manages authentication, RBAC authorizations, user lifecycles, and security auditing."""

    def __init__(self):
        self._ip_lockouts: Dict[str, Dict[str, Any]] = {}

    def _check_ip_lockout(self, ip_address: str):
        now = datetime.utcnow()
        ip_data = self._ip_lockouts.get(ip_address)
        if ip_data and ip_data.get("locked_until") and ip_data["locked_until"] > now:
            remaining_secs = int((ip_data["locked_until"] - now).total_seconds())
            mins = max(1, remaining_secs // 60)
            raise HTTPException(
                status_code=429,
                detail=f"Too many failed login attempts. Access temporarily restricted for {mins} minute(s)."
            )

    def _record_ip_failure(self, ip_address: str):
        now = datetime.utcnow()
        ip_data = self._ip_lockouts.get(ip_address, {"count": 0, "locked_until": None})
        ip_data["count"] += 1
        if ip_data["count"] >= MAX_FAILED_ATTEMPTS:
            ip_data["locked_until"] = now + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
            logger.warning(f"IP address {ip_address} locked out for {LOCKOUT_DURATION_MINUTES}m after {ip_data['count']} failed login attempts.")
        self._ip_lockouts[ip_address] = ip_data

    def _clear_ip_failure(self, ip_address: str):
        self._ip_lockouts.pop(ip_address, None)

    async def authenticate_user(self, username_or_email: str, password: str, ip_address: str = "127.0.0.1") -> Dict[str, Any]:
        self._check_ip_lockout(ip_address)

        env_user, env_pwd, _ = get_env_auth_credentials()
        is_env_auth = False
        target_prefix = ""
        correlation_id = uuid.uuid4().hex[:8]

        if env_user and env_pwd:
            input_clean = username_or_email.strip()
            input_norm = input_clean.lower()
            allowed_aliases = get_deterministic_username_aliases(env_user)

            # Prevent cross-domain spoofing: an email input with a different domain must NEVER match
            if "@" in input_clean and "@" in env_user:
                input_domain = input_norm.split("@", 1)[1]
                target_domain = env_user.strip().lower().split("@", 1)[1]
                user_matches = (input_domain == target_domain) and (input_norm in allowed_aliases)
            else:
                user_matches = (input_clean in allowed_aliases) or (input_norm in allowed_aliases)

            # Preserve exact cryptographic password comparison (strictly zero whitespace normalization)
            pwd_matches = hmac.compare_digest(password, env_pwd)

            target_prefix = env_user.split("@")[0] if "@" in env_user else env_user
            logger.info(
                f"[AUTH-{correlation_id}] Authentication evaluation completed for source {ip_address}: "
                f"outcome={'granted' if (user_matches and pwd_matches) else 'denied'}"
            )
            if user_matches and pwd_matches:
                is_env_auth = True

        async with async_session_maker() as session:
            if is_env_auth and env_user and env_pwd:
                # Provision or synchronize the designated .env admin user in PostgreSQL
                stmt = select(UserModel).where(
                    (UserModel.username == env_user) |
                    (UserModel.username == target_prefix) |
                    (UserModel.email == env_user) |
                    (UserModel.email == f"{target_prefix}@pravision.com") |
                    (UserModel.email == f"{env_user}@pravision.local")
                )
                user = (await session.execute(stmt)).scalars().first()
                clean_email = env_user if "@" in env_user else f"{env_user}@pravision.com"
                if not user:
                    user = UserModel(
                        username=env_user,
                        email=clean_email,
                        hashed_password=hash_password(env_pwd),
                        role="admin",
                        full_name="Platform Administrator",
                        is_active=True,
                        last_login=datetime.utcnow()
                    )
                    session.add(user)
                    await session.commit()
                    await session.refresh(user)
                else:
                    user.hashed_password = hash_password(env_pwd)
                    user.role = "admin"
                    user.is_active = True
                    user.failed_login_attempts = 0
                    user.locked_until = None
                    user.last_login = datetime.utcnow()
                    if user.email and "@pravision.local" in str(user.email) and "@" in env_user:
                        user.email = env_user
                    await session.commit()

                self._clear_ip_failure(ip_address)
                access_token = create_jwt_token(user.id, user.username, user.role, token_type="access")
                refresh_token = create_jwt_token(user.id, user.username, user.role, token_type="refresh")
                await self.record_audit("user_login", user.id, user.username, "auth", user.id, "success", {"role": user.role, "auth_source": "env"}, ip_address)

                return {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "token_type": "bearer",
                    "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                    "user": {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "role": user.role,
                        "full_name": user.full_name
                    }
                }

            # If not .env credentials, authenticate against standard provisioned database accounts
            input_clean = username_or_email.strip()
            input_lower = input_clean.lower()
            input_pfx = input_lower.split("@")[0]
            stmt = select(UserModel).where(
                (UserModel.username == input_clean) |
                (UserModel.username == input_lower) |
                (UserModel.username == input_pfx) |
                (UserModel.email == input_lower)
            )
            res = await session.execute(stmt)
            user = res.scalars().first()

            if not user:
                self._record_ip_failure(ip_address)
                await self.record_audit("user_login", None, username_or_email, "auth", None, "failure", {"reason": "user_not_found"}, ip_address)
                raise HTTPException(status_code=401, detail="Invalid username or password. Access denied.")

            # Check account lockout
            if user.locked_until and user.locked_until > datetime.utcnow():
                lock_mins = int((user.locked_until - datetime.utcnow()).total_seconds() / 60) + 1
                await self.record_audit("user_login", user.id, user.username, "auth", user.id, "denied", {"reason": "account_locked"}, ip_address)
                raise HTTPException(status_code=403, detail=f"Account is locked due to repeated failed attempts. Retry in {lock_mins} minute(s).")

            if not user.is_active:
                await self.record_audit("user_login", user.id, user.username, "auth", user.id, "denied", {"reason": "account_disabled"}, ip_address)
                raise HTTPException(status_code=403, detail="Account is disabled. Contact system administrator.")

            if not verify_password(password, user.hashed_password):
                user.failed_login_attempts += 1
                if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
                    user.locked_until = datetime.utcnow() + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
                    logger.warning(f"User '{user.username}' locked out for {LOCKOUT_DURATION_MINUTES}m after {user.failed_login_attempts} failed attempts.")
                await session.commit()
                self._record_ip_failure(ip_address)
                await self.record_audit("user_login", user.id, user.username, "auth", user.id, "failure", {"reason": "invalid_password", "failed_count": user.failed_login_attempts}, ip_address)
                raise HTTPException(status_code=401, detail="Invalid username or password. Access denied.")

            # Successful login: reset failed attempts on user and IP
            self._clear_ip_failure(ip_address)
            user.failed_login_attempts = 0
            user.locked_until = None
            user.last_login = datetime.utcnow()
            await session.commit()

            access_token = create_jwt_token(user.id, user.username, user.role, token_type="access")
            refresh_token = create_jwt_token(user.id, user.username, user.role, token_type="refresh")

            await self.record_audit("user_login", user.id, user.username, "auth", user.id, "success", {"role": user.role}, ip_address)

            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "role": user.role,
                    "full_name": user.full_name
                }
            }

    async def revoke_token(self, jti: str, exp_timestamp: int):
        async with async_session_maker() as session:
            revoked = RevokedTokenModel(
                token_jti=jti,
                expires_at=datetime.utcfromtimestamp(exp_timestamp)
            )
            session.add(revoked)
            await session.commit()

    async def is_token_revoked(self, jti: str) -> bool:
        async with async_session_maker() as session:
            stmt = select(RevokedTokenModel).where(RevokedTokenModel.token_jti == jti)
            res = await session.execute(stmt)
            return res.scalar_one_or_none() is not None

    async def create_user(
        self,
        username: str,
        email: str,
        password: str,
        role: str = "analyst",
        full_name: Optional[str] = None,
        creator_user: Optional[str] = None
    ) -> Dict[str, Any]:
        if role not in ("admin", "case_officer", "analyst"):
            raise ValueError(f"Invalid role '{role}'. Must be one of: admin, case_officer, analyst.")
        
        async with async_session_maker() as session:
            stmt = select(UserModel).where((UserModel.username == username.strip()) | (UserModel.email == email.strip().lower()))
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if existing:
                raise ValueError("User with this username or email already exists.")

            user = UserModel(
                username=username.strip(),
                email=email.strip().lower(),
                hashed_password=hash_password(password),
                role=role,
                full_name=full_name,
                is_active=True
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)

            await self.record_audit("create_user", None, creator_user or "system", "user", user.id, "success", {"username": user.username, "role": user.role})

            return {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "full_name": user.full_name,
                "is_active": user.is_active
            }

    async def list_users(self) -> List[Dict[str, Any]]:
        async with async_session_maker() as session:
            stmt = select(UserModel).order_by(UserModel.created_at.asc())
            users = (await session.execute(stmt)).scalars().all()
            return [
                {
                    "id": u.id,
                    "username": u.username,
                    "email": u.email,
                    "role": u.role,
                    "full_name": u.full_name,
                    "is_active": u.is_active,
                    "last_login": u.last_login.isoformat() if u.last_login else None,
                    "created_at": u.created_at.isoformat() if u.created_at else None
                }
                for u in users
            ]

    async def set_user_status(self, user_id: str, is_active: bool, actor: str) -> bool:
        async with async_session_maker() as session:
            stmt = select(UserModel).where(UserModel.id == user_id)
            user = (await session.execute(stmt)).scalar_one_or_none()
            if not user:
                return False
            user.is_active = is_active
            await session.commit()
            await self.record_audit("set_user_status", None, actor, "user", user_id, "success", {"is_active": is_active})
            return True

    async def set_user_role(self, user_id: str, new_role: str, actor: str) -> bool:
        if new_role not in ("admin", "case_officer", "analyst"):
            raise ValueError(f"Invalid role: {new_role}")
        async with async_session_maker() as session:
            stmt = select(UserModel).where(UserModel.id == user_id)
            user = (await session.execute(stmt)).scalar_one_or_none()
            if not user:
                return False
            user.role = new_role
            await session.commit()
            await self.record_audit("set_user_role", None, actor, "user", user_id, "success", {"new_role": new_role})
            return True

    async def seed_default_users(self):
        """Initializes default administrative and testing accounts if database is empty."""
        async with async_session_maker() as session:
            stmt = select(UserModel)
            count = len((await session.execute(stmt)).scalars().all())
            if count > 0:
                return

            logger.info("Initializing multi-user security credentials...")
            admin_pwd = validate_and_sanitize_initial_password(os.environ.get("ADMIN_INITIAL_PASSWORD"), "admin")
            officer_pwd = validate_and_sanitize_initial_password(os.environ.get("OFFICER_INITIAL_PASSWORD"), "officer")
            analyst_pwd = validate_and_sanitize_initial_password(os.environ.get("ANALYST_INITIAL_PASSWORD"), "analyst")

            # Write secure notice
            ADMIN_CREDS_FILE.write_text(
                f"ADMIN_USERNAME=admin\nADMIN_ROLE=admin\nOFFICER_USERNAME=case_officer\nANALYST_USERNAME=analyst\n",
                encoding="utf-8"
            )

            # Admin account
            admin = UserModel(
                username="admin",
                email="admin@pravision.local",
                hashed_password=hash_password(admin_pwd),
                role="admin",
                full_name="Chief Intelligence Administrator",
                is_active=True
            )
            # Case Officer account
            officer = UserModel(
                username="case_officer",
                email="officer@pravision.local",
                hashed_password=hash_password(officer_pwd),
                role="case_officer",
                full_name="Lead Investigation Officer",
                is_active=True
            )
            # Analyst account
            analyst = UserModel(
                username="analyst",
                email="analyst@pravision.local",
                hashed_password=hash_password(analyst_pwd),
                role="analyst",
                full_name="OSINT Field Analyst",
                is_active=True
            )
            session.add_all([admin, officer, analyst])
            await session.commit()
            logger.info("Default multi-user accounts provisioned (admin, case_officer, analyst).")

    async def record_audit(
        self,
        action: str,
        actor_id: Optional[str],
        user: str,
        target_type: Optional[str],
        target_id: Optional[str],
        outcome: str = "success",
        details: Optional[Dict[str, Any]] = None,
        ip_address: str = "127.0.0.1"
    ):
        """Persists security audit trail event with actor attribution."""
        try:
            async with async_session_maker() as session:
                log = AuditLogModel(
                    action=action,
                    actor_id=actor_id,
                    user=user,
                    target_type=target_type,
                    target_id=target_id,
                    outcome=outcome,
                    details=details or {},
                    ip_address=ip_address
                )
                session.add(log)
                await session.commit()
        except Exception as e:
            logger.warning(f"Audit log recording suppressed non-fatal error: {e}")

auth_service = AuthService()

# ----------------- FASTAPI RBAC DEPENDENCIES -----------------

async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_bearer)
) -> UserModel:
    """Extracts and verifies JWT token from Authorization header or cookie."""
    token = None
    if credentials:
        token = credentials.credentials
    elif "authorization" in request.headers or "Authorization" in request.headers:
        auth_head = request.headers.get("authorization") or request.headers.get("Authorization")
        if auth_head and auth_head.startswith("Bearer "):
            token = auth_head.split(" ", 1)[1].strip()
        elif auth_head:
            token = auth_head.strip()
    elif "pravision_session" in request.cookies:
        token = request.cookies.get("pravision_session")
    elif "pravision_token" in request.cookies:
        token = request.cookies.get("pravision_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    try:
        payload = decode_jwt_token(token)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {e}")

    jti = payload.get("jti")
    if jti and await auth_service.is_token_revoked(jti):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked.")

    user_id = payload.get("sub")
    async with async_session_maker() as session:
        stmt = select(UserModel).where(UserModel.id == user_id)
        user = (await session.execute(stmt)).scalar_one_or_none()
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User account is inactive or deleted.")
        return user

def require_role(allowed_roles: List[str]):
    """Enforces role-based permission check on route."""
    async def role_checker(current_user: UserModel = Depends(get_current_user)) -> UserModel:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Role '{current_user.role}' lacks permission for this operation. Requires one of: {allowed_roles}."
            )
        return current_user
    return role_checker

async def verify_case_access(
    case_id: str,
    user: UserModel,
    required_perm: str = "read"
) -> CaseModel:
    """
    Enforces granular case-level authorization:
    - Administrators have global read/write access.
    - Case officers can access cases they own or are assigned to.
    - Analysts can only access cases explicitly assigned to them in case_memberships.
    """
    async with async_session_maker() as session:
        stmt = select(CaseModel).options(selectinload(CaseModel.memberships)).where(CaseModel.id == case_id)
        case = (await session.execute(stmt)).scalar_one_or_none()
        if not case:
            raise HTTPException(status_code=404, detail="Case not found.")

        # Admin bypass
        if user.role == "admin":
            return case

        # Owner access
        if case.owner_id == user.id or case.created_by == user.username:
            return case

        # Check explicit membership in case_memberships
        membership = next((m for m in case.memberships if m.user_id == user.id), None)
        if membership:
            if required_perm == "read":
                return case
            if required_perm == "write" and membership.permission in ("owner", "editor"):
                return case

        # Access denied
        logger.warning(f"Unauthorized access attempt to case '{case_id}' by user '{user.username}' (role: {user.role})")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: You do not have permission to access case '{case_id}'."
        )
