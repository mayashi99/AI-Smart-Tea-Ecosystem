"""Database-backed roles, sessions, audit records, and passport ownership."""
import hashlib
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import psycopg2
from psycopg2.extras import DictCursor

from fastapi import HTTPException, Request


ROLES = (
    "admin",
    "export_manager",
    "quality_officer",
    "data_analyst",
    "farmer_seller",
    "viewer_buyer",
)

PERMISSIONS = {
    "home:view": set(ROLES),
    "dashboard:view": {"admin", "export_manager", "data_analyst", "viewer_buyer"},
    "market:view": {"admin", "export_manager", "data_analyst", "viewer_buyer"},
    "forecast:view": {"admin", "export_manager", "data_analyst", "viewer_buyer"},
    "usd_forecast:view": {"admin", "export_manager", "data_analyst", "viewer_buyer"},
    "readiness:view": {"admin", "export_manager", "quality_officer", "data_analyst", "farmer_seller"},
    "readiness:calculate": {"admin", "export_manager", "quality_officer", "farmer_seller"},
    "insights:view": {"admin", "export_manager", "data_analyst", "viewer_buyer"},
    "traceability:view": {"admin", "export_manager", "quality_officer", "farmer_seller"},
    "traceability:write": {"admin", "export_manager", "quality_officer", "farmer_seller"},
    "reports:view": {"admin", "export_manager", "quality_officer", "data_analyst", "farmer_seller", "viewer_buyer"},
    "settings:view": {"admin"},
    "users:manage": {"admin"},
    "zone_score:calculate": {"admin", "export_manager", "data_analyst"},
}

SESSION_COOKIE = "tea_session"
CSRF_COOKIE = "tea_csrf"


class _ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


class _PostgresConnection:
    def __init__(self, connection):
        self._connection = connection

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            if exc_type is None:
                self._connection.commit()
            else:
                self._connection.rollback()
        finally:
            self._connection.close()
        return False

    def execute(self, sql: str, parameters=()):
        cursor = self._connection.cursor()
        if sql.strip().upper() == "BEGIN IMMEDIATE":
            cursor.execute("SELECT pg_advisory_xact_lock(846292341)")
            return cursor
        cursor.execute(sql.replace("?", "%s"), parameters)
        return cursor


def _database_path() -> Path:
    configured = os.getenv("RBAC_DATABASE_PATH")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[2] / "data" / "rbac.sqlite3"


def _postgres_dsn(database_url: str) -> str:
    parts = urlsplit(database_url)
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() != "channel_binding" or value.strip()
    ]
    return urlunsplit(parts._replace(query=urlencode(query)))


def _initialize_postgres(connection: _PostgresConnection) -> None:
    statements = (
        """CREATE TABLE IF NOT EXISTS users (
            id BIGSERIAL PRIMARY KEY,
            email TEXT NOT NULL,
            display_name TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN (
                'admin', 'export_manager', 'quality_officer',
                'data_analyst', 'farmer_seller', 'viewer_buyer'
            )),
            active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
            is_super_admin INTEGER NOT NULL DEFAULT 0 CHECK (is_super_admin IN (0, 1)),
            approval_status TEXT NOT NULL DEFAULT 'approved' CHECK (approval_status IN ('pending', 'approved', 'rejected')),
            password_hash TEXT,
            totp_secret_encrypted TEXT,
            totp_enabled INTEGER NOT NULL DEFAULT 0 CHECK (totp_enabled IN (0, 1)),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY,
            csrf_token TEXT NOT NULL,
            user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS oauth_states (
            state_hash TEXT PRIMARY KEY,
            nonce TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            intent TEXT NOT NULL DEFAULT 'login',
            requested_role TEXT NOT NULL DEFAULT 'viewer_buyer',
            login_email TEXT,
            requested_name TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS admin_auth_challenges (
            token_hash TEXT PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            purpose TEXT NOT NULL CHECK (purpose IN ('enroll', 'login')),
            secret_encrypted TEXT,
            attempts INTEGER NOT NULL DEFAULT 0,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS audit_log (
            id BIGSERIAL PRIMARY KEY,
            actor_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
            actor_email TEXT,
            action TEXT NOT NULL,
            target_type TEXT,
            target_id TEXT,
            outcome TEXT NOT NULL,
            details TEXT,
            created_at TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS passport_batches (
            batch_id TEXT PRIMARY KEY,
            owner_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
            public_id TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL
        )""",
        "CREATE UNIQUE INDEX IF NOT EXISTS users_email_lower_unique ON users (LOWER(email))",
    )
    for statement in statements:
        connection.execute(statement)
    for table, name, sql_type in (
        ("users", "is_super_admin", "INTEGER NOT NULL DEFAULT 0"),
        ("users", "approval_status", "TEXT NOT NULL DEFAULT 'approved'"),
        ("users", "password_hash", "TEXT"),
        ("users", "totp_secret_encrypted", "TEXT"),
        ("users", "totp_enabled", "INTEGER NOT NULL DEFAULT 0"),
        ("oauth_states", "intent", "TEXT NOT NULL DEFAULT 'login'"),
        ("oauth_states", "requested_role", "TEXT NOT NULL DEFAULT 'viewer_buyer'"),
        ("oauth_states", "login_email", "TEXT"),
        ("oauth_states", "requested_name", "TEXT"),
        ("admin_auth_challenges", "attempts", "INTEGER NOT NULL DEFAULT 0"),
    ):
        connection.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {name} {sql_type}")


def connect() -> sqlite3.Connection | _PostgresConnection:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url and not os.getenv("RBAC_DATABASE_PATH"):
        connection = _PostgresConnection(
            psycopg2.connect(_postgres_dsn(database_url), sslmode="require", cursor_factory=DictCursor)
        )
        try:
            _initialize_postgres(connection)
        except Exception:
            connection._connection.rollback()
            connection._connection.close()
            raise
        return connection

    path = _database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=15, factory=_ClosingConnection)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 15000")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            display_name TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN (
                'admin', 'export_manager', 'quality_officer',
                'data_analyst', 'farmer_seller', 'viewer_buyer'
            )),
            active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
            is_super_admin INTEGER NOT NULL DEFAULT 0 CHECK (is_super_admin IN (0, 1)),
            approval_status TEXT NOT NULL DEFAULT 'approved' CHECK (approval_status IN ('pending', 'approved', 'rejected')),
            password_hash TEXT,
            totp_secret_encrypted TEXT,
            totp_enabled INTEGER NOT NULL DEFAULT 0 CHECK (totp_enabled IN (0, 1)),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY,
            csrf_token TEXT NOT NULL,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS oauth_states (
            state_hash TEXT PRIMARY KEY,
            nonce TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            intent TEXT NOT NULL DEFAULT 'login',
            requested_role TEXT NOT NULL DEFAULT 'viewer_buyer',
            login_email TEXT,
            requested_name TEXT
        );
        CREATE TABLE IF NOT EXISTS admin_auth_challenges (
            token_hash TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            purpose TEXT NOT NULL CHECK (purpose IN ('enroll', 'login')),
            secret_encrypted TEXT,
            attempts INTEGER NOT NULL DEFAULT 0,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY,
            actor_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            actor_email TEXT,
            action TEXT NOT NULL,
            target_type TEXT,
            target_id TEXT,
            outcome TEXT NOT NULL,
            details TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS passport_batches (
            batch_id TEXT PRIMARY KEY,
            owner_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            public_id TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL
        );
        """
    )
    user_columns = {row["name"] for row in connection.execute("PRAGMA table_info(users)")}
    for name, sql_type in (
        ("is_super_admin", "INTEGER NOT NULL DEFAULT 0"),
        ("approval_status", "TEXT NOT NULL DEFAULT 'approved'"),
        ("password_hash", "TEXT"),
        ("totp_secret_encrypted", "TEXT"),
        ("totp_enabled", "INTEGER NOT NULL DEFAULT 0"),
    ):
        if name not in user_columns:
            connection.execute(f"ALTER TABLE users ADD COLUMN {name} {sql_type}")
    oauth_columns = {row["name"] for row in connection.execute("PRAGMA table_info(oauth_states)")}
    for name, sql_type in (
        ("intent", "TEXT NOT NULL DEFAULT 'login'"),
        ("requested_role", "TEXT NOT NULL DEFAULT 'viewer_buyer'"),
        ("login_email", "TEXT"),
        ("requested_name", "TEXT"),
    ):
        if name not in oauth_columns:
            connection.execute(f"ALTER TABLE oauth_states ADD COLUMN {name} {sql_type}")
    challenge_columns = {row["name"] for row in connection.execute("PRAGMA table_info(admin_auth_challenges)")}
    if "attempts" not in challenge_columns:
        connection.execute("ALTER TABLE admin_auth_challenges ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0")
    return connection


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_time(value: datetime | None = None) -> str:
    return (value or utc_now()).isoformat()


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def new_opaque_id() -> str:
    return secrets.token_urlsafe(32)


def get_user_by_email(email: str) -> Any | None:
    with connect() as connection:
        return connection.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()


def get_user_by_id(user_id: int) -> Any | None:
    with connect() as connection:
        return connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def is_bootstrapped() -> bool:
    with connect() as connection:
        return connection.execute("SELECT 1 FROM users WHERE is_super_admin = 1 LIMIT 1").fetchone() is not None


def audit(
    action: str,
    *,
    actor: dict | None = None,
    target_type: str | None = None,
    target_id: str | int | None = None,
    outcome: str = "success",
    details: str | None = None,
) -> None:
    with connect() as connection:
        connection.execute(
            """INSERT INTO audit_log
               (actor_user_id, actor_email, action, target_type, target_id, outcome, details, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                actor.get("id") if actor else None,
                actor.get("email") if actor else None,
                action,
                target_type,
                str(target_id) if target_id is not None else None,
                outcome,
                details,
                iso_time(),
            ),
        )


def create_session(user_id: int) -> tuple[str, str]:
    token = new_opaque_id()
    csrf_token = new_opaque_id()
    now = utc_now()
    with connect() as connection:
        connection.execute(
            "INSERT INTO sessions (token_hash, csrf_token, user_id, expires_at, created_at) VALUES (?, ?, ?, ?, ?)",
            (digest(token), csrf_token, user_id, iso_time(now + timedelta(hours=12)), iso_time(now)),
        )
    return token, csrf_token


def user_from_request(request: Request) -> dict:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Sign in is required")
    token_hash = digest(token)
    with connect() as connection:
        row = connection.execute(
            """SELECT users.id, users.email, users.display_name, users.role, users.active,
                      users.is_super_admin, users.approval_status,
                      sessions.csrf_token, sessions.expires_at
               FROM sessions JOIN users ON users.id = sessions.user_id
               WHERE sessions.token_hash = ?""",
            (token_hash,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=401, detail="Session is not valid")
        if not row["active"]:
            connection.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
            raise HTTPException(status_code=401, detail="This account has been deactivated")
        if row["approval_status"] != "approved":
            connection.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
            raise HTTPException(status_code=403, detail="This account is awaiting role approval")
        if datetime.fromisoformat(row["expires_at"]) <= utc_now():
            connection.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
            raise HTTPException(status_code=401, detail="Session has expired")
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            cookie_csrf = request.cookies.get(CSRF_COOKIE)
            header_csrf = request.headers.get("x-csrf-token")
            if (
                not cookie_csrf
                or not header_csrf
                or not secrets.compare_digest(cookie_csrf, row["csrf_token"])
                or not secrets.compare_digest(header_csrf, row["csrf_token"])
            ):
                raise HTTPException(status_code=403, detail="CSRF token is missing or invalid")
        return dict(row)


def require_permission(permission: str):
    allowed_roles = PERMISSIONS.get(permission)
    if allowed_roles is None:
        raise ValueError(f"Unknown permission: {permission}")

    def dependency(request: Request) -> dict:
        user = user_from_request(request)
        if user["role"] not in allowed_roles:
            raise HTTPException(status_code=403, detail="You do not have permission to access this resource")
        return user

    return dependency


def require_user_management(request: Request) -> dict:
    return require_permission("users:manage")(request)


def ensure_passport_batch(batch_id: str, owner_user_id: int | None = None) -> dict:
    with connect() as connection:
        row = connection.execute(
            "SELECT batch_id, owner_user_id, public_id FROM passport_batches WHERE batch_id = ?",
            (batch_id,),
        ).fetchone()
        if row:
            return dict(row)
        value = {
            "batch_id": batch_id,
            "owner_user_id": owner_user_id,
            "public_id": new_opaque_id(),
        }
        connection.execute(
            "INSERT INTO passport_batches (batch_id, owner_user_id, public_id, created_at) VALUES (?, ?, ?, ?)",
            (batch_id, owner_user_id, value["public_id"], iso_time()),
        )
        return value


def get_passport_batch(batch_id: str) -> dict | None:
    with connect() as connection:
        row = connection.execute(
            "SELECT batch_id, owner_user_id, public_id FROM passport_batches WHERE batch_id = ?",
            (batch_id,),
        ).fetchone()
        return dict(row) if row else None


def get_public_batch(public_id: str) -> dict | None:
    with connect() as connection:
        row = connection.execute(
            "SELECT batch_id, owner_user_id, public_id FROM passport_batches WHERE public_id = ?",
            (public_id,),
        ).fetchone()
        return dict(row) if row else None


def list_audit_events(*, limit: int = 100, user_id: int | None = None) -> list[dict]:
    limit = max(1, min(limit, 500))
    with connect() as connection:
        if user_id is None:
            rows = connection.execute(
                "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        else:
            rows = connection.execute(
                "SELECT * FROM audit_log WHERE actor_user_id = ? ORDER BY id DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]


def role_has_permission(role: str, permission: str) -> bool:
    return role in PERMISSIONS.get(permission, set())
