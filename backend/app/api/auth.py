"""Google OAuth sign-in, role-aware registration, and user administration."""
import base64
import hashlib
import hmac
import io
import os
import secrets
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal
from urllib.parse import quote, urlencode

import psycopg2
import qrcode
import requests
from cryptography.fernet import Fernet, InvalidToken
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, EmailStr, Field

from app.core.rbac import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    audit,
    connect,
    create_session,
    digest,
    get_user_by_email,
    iso_time,
    list_audit_events,
    require_user_management,
    require_permission,
    user_from_request,
    utc_now,
)

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

router = APIRouter(prefix="/api/auth", tags=["authentication"])


class UserCreateRequest(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=100)
    role: Literal["export_manager", "quality_officer", "data_analyst", "farmer_seller", "viewer_buyer"]


class UserUpdateRequest(BaseModel):
    role: Literal["export_manager", "quality_officer", "data_analyst", "farmer_seller", "viewer_buyer"] | None = None
    active: bool | None = None


class ApprovalRequest(BaseModel):
    status: Literal["approved", "rejected"]


class AdminPasswordRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class TotpVerifyRequest(BaseModel):
    challenge_id: str = Field(min_length=32, max_length=128)
    code: str = Field(pattern=r"^\d{6}$")


def _frontend_url(path: str) -> str:
    base = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
    return f"{base}{path}"


def _cookie_secure() -> bool:
    return os.getenv("COOKIE_SECURE", "false").strip().lower() in {"1", "true", "yes"}


def _set_session_cookies(response: Response, token: str, csrf_token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
        max_age=12 * 60 * 60,
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        httponly=False,
        secure=_cookie_secure(),
        samesite="lax",
        max_age=12 * 60 * 60,
        path="/",
    )


def _new_session_redirect(user: dict) -> RedirectResponse:
    token, csrf_token = create_session(user["id"])
    audit("login", actor=dict(user), target_type="user", target_id=user["id"])
    response = RedirectResponse(_frontend_url("/"), status_code=303)
    _set_session_cookies(response, token, csrf_token)
    return response


def _oauth_settings() -> tuple[str, str, str]:
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "").strip()
    if not client_id or not client_secret or not redirect_uri:
        raise HTTPException(status_code=503, detail="Google sign-in is not configured")
    return client_id, client_secret, redirect_uri


def _password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    value = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(value).decode()}"


def _verify_password(password: str, stored_hash: str | None) -> bool:
    if not stored_hash:
        return False
    try:
        algorithm, encoded_salt, encoded_value = stored_hash.split("$", 2)
        if algorithm != "scrypt":
            return False
        expected = base64.urlsafe_b64decode(encoded_value.encode())
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=base64.urlsafe_b64decode(encoded_salt.encode()),
            n=2**14,
            r=8,
            p=1,
        )
    except (ValueError, TypeError):
        return False
    return secrets.compare_digest(actual, expected)


def _totp_cipher() -> Fernet:
    key = os.getenv("TOTP_ENCRYPTION_KEY", "").strip()
    if not key:
        raise HTTPException(status_code=503, detail="TOTP_ENCRYPTION_KEY is not configured")
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise HTTPException(status_code=503, detail="TOTP_ENCRYPTION_KEY is invalid") from exc


def _encrypt_totp_secret(secret: str) -> str:
    return _totp_cipher().encrypt(secret.encode("ascii")).decode("ascii")


def _decrypt_totp_secret(value: str) -> str:
    try:
        return _totp_cipher().decrypt(value.encode("ascii")).decode("ascii")
    except InvalidToken as exc:
        raise HTTPException(status_code=503, detail="Stored authenticator key could not be decrypted") from exc


def _new_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _totp_code(secret: str, timestamp: float | None = None) -> str:
    step = int((timestamp if timestamp is not None else time.time()) // 30)
    key = base64.b32decode(secret + "=" * (-len(secret) % 8))
    message = step.to_bytes(8, "big")
    digest_value = hmac.new(key, message, hashlib.sha1).digest()
    offset = digest_value[-1] & 0x0F
    value = int.from_bytes(digest_value[offset:offset + 4], "big") & 0x7FFFFFFF
    return f"{value % 1_000_000:06d}"


def _verify_totp(secret: str, code: str) -> bool:
    now = time.time()
    return any(secrets.compare_digest(_totp_code(secret, now + window * 30), code) for window in (-1, 0, 1))


def _ensure_bootstrap_super_admin() -> None:
    now = iso_time()
    with connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        existing_super_admin = connection.execute(
            "SELECT id FROM users WHERE is_super_admin = 1 LIMIT 1"
        ).fetchone()
        if existing_super_admin:
            return
        email = os.getenv("ADMIN_BOOTSTRAP_EMAIL", "admin@gmail.com").strip().lower()
        password = os.getenv("ADMIN_BOOTSTRAP_PASSWORD", "")
        if not email or not password:
            raise HTTPException(
                status_code=503,
                detail="Set ADMIN_BOOTSTRAP_EMAIL and ADMIN_BOOTSTRAP_PASSWORD before signing in as Super Admin",
            )
        encoded_password = _password_hash(password)
        existing = connection.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            connection.execute(
                """UPDATE users SET role = 'admin', is_super_admin = 1, approval_status = 'approved',
                   active = 1, password_hash = ?, updated_at = ? WHERE id = ?""",
                (encoded_password, now, existing["id"]),
            )
        else:
            connection.execute(
                """INSERT INTO users
                   (email, display_name, role, active, is_super_admin, approval_status, password_hash, created_at, updated_at)
                   VALUES (?, 'Super Admin', 'admin', 1, 1, 'approved', ?, ?, ?)""",
                (email, encoded_password, now, now),
            )


@router.post("/admin/login")
def admin_password_login(payload: AdminPasswordRequest):
    _ensure_bootstrap_super_admin()
    email = str(payload.email).strip().lower()
    user = get_user_by_email(email)
    if not user or not user["is_super_admin"] or not _verify_password(payload.password, user["password_hash"]):
        audit("super_admin_login", actor={"email": email}, target_type="user", outcome="denied", details="Invalid credentials")
        raise HTTPException(status_code=401, detail="Email or password is incorrect")
    if not user["active"] or user["approval_status"] != "approved":
        raise HTTPException(status_code=403, detail="This Super Admin account is inactive")

    challenge_id = secrets.token_urlsafe(32)
    now = utc_now()
    with connect() as connection:
        connection.execute("DELETE FROM admin_auth_challenges WHERE expires_at <= ?", (iso_time(now),))
        if user["totp_enabled"]:
            connection.execute(
                """INSERT INTO admin_auth_challenges
                   (token_hash, user_id, purpose, secret_encrypted, expires_at, created_at)
                   VALUES (?, ?, 'login', NULL, ?, ?)""",
                (digest(challenge_id), user["id"], iso_time(now + timedelta(minutes=5)), iso_time(now)),
            )
            return {"setup_required": False, "challenge_id": challenge_id}

        secret = _new_totp_secret()
        connection.execute(
            """INSERT INTO admin_auth_challenges
               (token_hash, user_id, purpose, secret_encrypted, expires_at, created_at)
               VALUES (?, ?, 'enroll', ?, ?, ?)""",
            (
                digest(challenge_id),
                user["id"],
                _encrypt_totp_secret(secret),
                iso_time(now + timedelta(minutes=10)),
                iso_time(now),
            ),
        )

    issuer = "TeaExportAI"
    otpauth_uri = (
        f"otpauth://totp/{quote(issuer, safe='')}:{quote(email, safe='')}"
        f"?secret={secret}&issuer={quote(issuer, safe='')}&algorithm=SHA1&digits=6&period=30"
    )
    image = qrcode.make(otpauth_uri)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    qr_code = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
    return {
        "setup_required": True,
        "challenge_id": challenge_id,
        "qr_code": qr_code,
        "manual_entry_key": secret,
    }


@router.post("/admin/login/verify")
def admin_totp_verify(payload: TotpVerifyRequest, response: Response):
    challenge_hash = digest(payload.challenge_id)
    now = utc_now()
    invalid_code = False
    expired = False
    with connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        challenge = connection.execute(
            "SELECT * FROM admin_auth_challenges WHERE token_hash = ?",
            (challenge_hash,),
        ).fetchone()
        if challenge is None:
            raise HTTPException(status_code=401, detail="Authenticator verification expired; sign in again")
        if datetime.fromisoformat(challenge["expires_at"]) <= now:
            connection.execute("DELETE FROM admin_auth_challenges WHERE token_hash = ?", (challenge_hash,))
            expired = True
        user = connection.execute("SELECT * FROM users WHERE id = ?", (challenge["user_id"],)).fetchone()
        if not expired and (user is None or not user["active"] or not user["is_super_admin"]):
            connection.execute("DELETE FROM admin_auth_challenges WHERE token_hash = ?", (challenge_hash,))
            expired = True
        if not expired:
            secret_encrypted = challenge["secret_encrypted"] if challenge["purpose"] == "enroll" else user["totp_secret_encrypted"]
            if not secret_encrypted:
                connection.execute("DELETE FROM admin_auth_challenges WHERE token_hash = ?", (challenge_hash,))
                expired = True
            else:
                secret = _decrypt_totp_secret(secret_encrypted)
                if not _verify_totp(secret, payload.code):
                    attempts = challenge["attempts"] + 1
                    if attempts >= 5:
                        connection.execute("DELETE FROM admin_auth_challenges WHERE token_hash = ?", (challenge_hash,))
                    else:
                        connection.execute(
                            "UPDATE admin_auth_challenges SET attempts = ? WHERE token_hash = ?",
                            (attempts, challenge_hash),
                        )
                    invalid_code = True
                else:
                    connection.execute("DELETE FROM admin_auth_challenges WHERE token_hash = ?", (challenge_hash,))
                    if challenge["purpose"] == "enroll":
                        connection.execute(
                            "UPDATE users SET totp_secret_encrypted = ?, totp_enabled = 1, updated_at = ? WHERE id = ?",
                            (secret_encrypted, iso_time(), user["id"]),
                        )
                        user = connection.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()

    if expired:
        raise HTTPException(status_code=401, detail="Authenticator verification expired; sign in again")
    if invalid_code:
        audit("super_admin_totp", actor=dict(user), target_type="user", target_id=user["id"], outcome="denied")
        raise HTTPException(status_code=401, detail="Authenticator code is incorrect")
    if challenge["purpose"] == "enroll":
        audit("super_admin_totp_enrolled", actor=dict(user), target_type="user", target_id=user["id"])

    token, csrf_token = create_session(user["id"])
    _set_session_cookies(response, token, csrf_token)
    audit("login", actor=dict(user), target_type="user", target_id=user["id"])
    return {"authenticated": True, "role": "admin", "is_super_admin": True}


@router.get("/google/start")
def google_login_start(
    intent: Literal["login", "signup"] = "login",
    email: EmailStr | None = None,
    display_name: str | None = Query(default=None, max_length=100),
    role: Literal[
        "admin",
        "export_manager",
        "quality_officer",
        "data_analyst",
        "farmer_seller",
        "viewer_buyer",
    ] = "viewer_buyer",
):
    client_id, _, redirect_uri = _oauth_settings()
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    expiry = iso_time(utc_now() + timedelta(minutes=10))
    with connect() as connection:
        connection.execute("DELETE FROM oauth_states WHERE expires_at <= ?", (iso_time(),))
        connection.execute(
            """INSERT INTO oauth_states
               (state_hash, nonce, expires_at, intent, requested_role, login_email, requested_name)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (digest(state), nonce, expiry, intent, role, str(email).lower() if email else None, display_name.strip() if display_name else None),
        )
    oauth_parameters = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
        "prompt": "select_account",
    }
    if email:
        oauth_parameters["login_hint"] = str(email)
    parameters = urlencode(oauth_parameters)
    response = RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{parameters}", status_code=302)
    response.set_cookie(
        "tea_oauth_state",
        state,
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
        max_age=600,
        path="/api/auth/google",
    )
    return response


@router.get("/google/callback")
def google_login_callback(request: Request, code: str, state: str):
    state_cookie = request.cookies.get("tea_oauth_state")
    if not state_cookie or not secrets.compare_digest(state, state_cookie):
        raise HTTPException(status_code=400, detail="OAuth state validation failed")
    with connect() as connection:
        oauth_state = connection.execute(
            "SELECT nonce, expires_at, intent, requested_role, login_email, requested_name FROM oauth_states WHERE state_hash = ?",
            (digest(state),),
        ).fetchone()
        connection.execute("DELETE FROM oauth_states WHERE state_hash = ?", (digest(state),))
    if oauth_state is None or datetime.fromisoformat(oauth_state["expires_at"]) <= utc_now():
        raise HTTPException(status_code=400, detail="OAuth sign-in expired; try again")

    client_id, client_secret, redirect_uri = _oauth_settings()
    try:
        from google.auth.exceptions import GoogleAuthError
        token_response = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=10,
        )
        token_response.raise_for_status()
        id_token = token_response.json()["id_token"]
        from google.auth.transport.requests import Request as GoogleRequest
        from google.oauth2 import id_token as google_id_token

        claims = google_id_token.verify_oauth2_token(id_token, GoogleRequest(), client_id)
    except (requests.RequestException, KeyError, ValueError, GoogleAuthError) as exc:
        raise HTTPException(status_code=401, detail="Google sign-in could not be verified") from exc
    if claims.get("nonce") != oauth_state["nonce"] or claims.get("email_verified") is not True:
        raise HTTPException(status_code=401, detail="Google account verification failed")

    email = str(claims.get("email", "")).strip().lower()
    if not email:
        raise HTTPException(status_code=401, detail="Google did not provide a verified email address")
    display_name = str(oauth_state["requested_name"] or claims.get("name") or email).strip()[:100]
    if oauth_state["login_email"] and not secrets.compare_digest(email, oauth_state["login_email"]):
        audit("login", actor={"email": email}, target_type="user", outcome="denied", details="Google identity did not match the entered email")
        return RedirectResponse(_frontend_url("/login?error=email-mismatch"), status_code=303)

    user = get_user_by_email(email)
    if user is None and oauth_state["intent"] == "signup":
        now = iso_time()
        requested_role = oauth_state["requested_role"]
        approval_status = "pending" if requested_role in {
            "admin",
            "export_manager",
            "quality_officer",
            "data_analyst",
        } else "approved"
        with connect() as connection:
            cursor = connection.execute(
                """INSERT INTO users
                   (email, display_name, role, active, approval_status, created_at, updated_at)
                   VALUES (?, ?, ?, 1, ?, ?, ?) RETURNING id""",
                (email, display_name, requested_role, approval_status, now, now),
            )
            user_id = cursor.fetchone()["id"]
        user = {
            "id": user_id,
            "email": email,
            "display_name": display_name,
            "role": requested_role,
            "active": 1,
            "approval_status": approval_status,
            "is_super_admin": 0,
        }
        audit("user_self_registered", actor=user, target_type="user", target_id=user_id, details=f"role={user['role']}; status={approval_status}")

    if user is not None:
        if user["is_super_admin"]:
            return RedirectResponse(_frontend_url("/login?error=super-admin-password"), status_code=303)
        if not user["active"]:
            audit("login", actor={"id": user["id"], "email": email}, target_type="user", target_id=user["id"], outcome="denied", details="Account deactivated")
            return RedirectResponse(_frontend_url("/login?error=account-disabled"), status_code=303)
        if user["approval_status"] != "approved":
            error = "pending-approval" if user["approval_status"] == "pending" else "request-rejected"
            return RedirectResponse(_frontend_url(f"/login?error={error}"), status_code=303)
        response = _new_session_redirect(dict(user))
        response.delete_cookie("tea_oauth_state", path="/api/auth/google")
        return response

    audit("login", actor={"email": email}, target_type="user", outcome="denied", details="Account is not registered")
    error = "not-invited" if oauth_state["intent"] == "login" else "signup-failed"
    return RedirectResponse(_frontend_url(f"/login?error={error}"), status_code=303)


@router.get("/me")
def current_session(request: Request):
    user = user_from_request(request)
    return {
        "id": user["id"],
        "email": user["email"],
        "display_name": user["display_name"],
        "role": user["role"],
        "is_super_admin": bool(user["is_super_admin"]),
    }


ROLE_LABELS = {
    "admin": "Admin",
    "export_manager": "Export Manager",
    "quality_officer": "Quality & Compliance Officer",
    "data_analyst": "Data Analyst",
    "farmer_seller": "Farmer / Seller",
    "viewer_buyer": "Viewer / Buyer",
}


@router.get("/role-hint")
def role_hint(email: EmailStr = Query()):
    account = get_user_by_email(str(email).strip().lower())
    status = account["approval_status"] if account and account["active"] else None
    role = ROLE_LABELS.get(account["role"]) if account and account["active"] else None
    return {"role": role, "approval_status": status}


@router.post("/logout")
def logout(request: Request, user: dict = Depends(user_from_request)):
    token = request.cookies.get(SESSION_COOKIE)
    with connect() as connection:
        connection.execute("DELETE FROM sessions WHERE token_hash = ?", (digest(token),))
    audit("logout", actor=user, target_type="user", target_id=user["id"])
    response = JSONResponse({"ok": True})
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    return response


@router.get("/users")
def list_users(user: dict = Depends(require_user_management)):
    with connect() as connection:
        rows = connection.execute(
            """SELECT id, email, display_name, role, active, is_super_admin, approval_status,
                      created_at, updated_at FROM users ORDER BY email"""
        ).fetchall()
    return {"users": [dict(row) for row in rows]}


@router.get("/user-requests")
def list_user_requests(user: dict = Depends(require_user_management)):
    with connect() as connection:
        rows = connection.execute(
            """SELECT id, email, display_name, role, created_at
               FROM users WHERE approval_status = 'pending' ORDER BY created_at"""
        ).fetchall()
    return {"requests": [dict(row) for row in rows]}


@router.patch("/users/{target_user_id}/approval")
def decide_user_request(
    target_user_id: int,
    payload: ApprovalRequest,
    user: dict = Depends(require_user_management),
):
    with connect() as connection:
        target = connection.execute("SELECT * FROM users WHERE id = ?", (target_user_id,)).fetchone()
        if target is None:
            raise HTTPException(status_code=404, detail="User request not found")
        if target["approval_status"] != "pending":
            raise HTTPException(status_code=409, detail="This access request has already been reviewed")
        if target["role"] == "admin" and not user["is_super_admin"]:
            raise HTTPException(status_code=403, detail="Only the Super Admin can approve Admin requests")
        connection.execute(
            "UPDATE users SET approval_status = ?, updated_at = ? WHERE id = ?",
            (payload.status, iso_time(), target_user_id),
        )
    audit(
        "user_access_request_reviewed",
        actor=user,
        target_type="user",
        target_id=target_user_id,
        details=f"role={target['role']}; status={payload.status}",
    )
    return {"id": target_user_id, "role": target["role"], "approval_status": payload.status}


@router.post("/users", status_code=201)
def create_user(payload: UserCreateRequest, user: dict = Depends(require_user_management)):
    now = iso_time()
    email = str(payload.email).strip().lower()
    try:
        with connect() as connection:
            cursor = connection.execute(
                "INSERT INTO users (email, display_name, role, active, created_at, updated_at) VALUES (?, ?, ?, 1, ?, ?) RETURNING id",
                (email, payload.display_name.strip(), payload.role, now, now),
            )
            user_id = cursor.fetchone()["id"]
    except (sqlite3.IntegrityError, psycopg2.IntegrityError) as exc:
        raise HTTPException(status_code=409, detail="A user with that email already exists") from exc
    audit("user_created", actor=user, target_type="user", target_id=user_id, details=f"role={payload.role}")
    return {"id": user_id, "email": email, "display_name": payload.display_name.strip(), "role": payload.role, "active": True}


@router.patch("/users/{target_user_id}")
def update_user(
    target_user_id: int,
    payload: UserUpdateRequest,
    user: dict = Depends(require_user_management),
):
    if payload.role is None and payload.active is None:
        raise HTTPException(status_code=422, detail="Provide a role or active status to update")
    with connect() as connection:
        target = connection.execute("SELECT * FROM users WHERE id = ?", (target_user_id,)).fetchone()
        if target is None:
            raise HTTPException(status_code=404, detail="User not found")
        updated_role = payload.role or target["role"]
        updated_active = target["active"] if payload.active is None else int(payload.active)
        if target["is_super_admin"]:
            raise HTTPException(status_code=409, detail="The Super Admin account cannot be changed or deactivated")
        if target["role"] == "admin" and not user["is_super_admin"]:
            raise HTTPException(status_code=403, detail="Only the Super Admin can manage Admin accounts")
        if updated_role == "admin" and target["role"] != "admin":
            raise HTTPException(status_code=409, detail="Admin access must be granted through an approved role request")
        if target_user_id == user["id"] and not updated_active:
            raise HTTPException(status_code=409, detail="You cannot deactivate your own account")
        if target["role"] == "admin" and target["active"] and (updated_role != "admin" or not updated_active):
            active_admins = connection.execute(
                "SELECT COUNT(*) FROM users WHERE role = 'admin' AND active = 1"
            ).fetchone()[0]
            if active_admins <= 1:
                raise HTTPException(status_code=409, detail="The last active administrator cannot be demoted or deactivated")
        connection.execute(
            "UPDATE users SET role = ?, active = ?, updated_at = ? WHERE id = ?",
            (updated_role, updated_active, iso_time(), target_user_id),
        )
        if not updated_active:
            connection.execute("DELETE FROM sessions WHERE user_id = ?", (target_user_id,))
    if payload.role is not None and payload.role != target["role"]:
        audit("user_role_changed", actor=user, target_type="user", target_id=target_user_id, details=f"role={payload.role}")
    if payload.active is False and target["active"]:
        audit("user_deactivated", actor=user, target_type="user", target_id=target_user_id)
    if payload.active is True and not target["active"]:
        audit("user_activated", actor=user, target_type="user", target_id=target_user_id)
    updated = get_user_by_email(target["email"])
    return {key: updated[key] for key in ("id", "email", "display_name", "role", "active", "created_at", "updated_at")}


@router.get("/audit")
def get_audit_log(
    limit: int = 100,
    user_id: int | None = None,
    user: dict = Depends(require_user_management),
):
    return {"events": list_audit_events(limit=limit, user_id=user_id)}


class ReportExportRequest(BaseModel):
    report_id: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9-]+$")
    format: Literal["csv", "json", "pdf"] = "csv"


@router.post("/report-export")
def record_report_export(
    payload: ReportExportRequest,
    user: dict = Depends(require_permission("reports:view")),
):
    audit(
        "report_exported",
        actor=user,
        target_type="report",
        target_id=payload.report_id,
        details=f"format={payload.format}",
    )
    return {"ok": True}
