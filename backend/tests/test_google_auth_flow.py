import os
import tempfile
import unittest
from http.cookies import SimpleCookie
from pathlib import Path
from unittest.mock import patch

from cryptography.fernet import Fernet
from starlette.requests import Request

from app.api import auth
from app.core import rbac


class GoogleAuthFlowTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "rbac.sqlite3"
        self.environment = patch.dict(os.environ, {
            "RBAC_DATABASE_PATH": str(self.database_path),
            "GOOGLE_CLIENT_ID": "test-client-id",
            "GOOGLE_CLIENT_SECRET": "test-client-secret",
            "GOOGLE_REDIRECT_URI": "http://localhost:8000/api/auth/google/callback",
            "FRONTEND_URL": "http://localhost:5173",
            "COOKIE_SECURE": "false",
            "TOTP_ENCRYPTION_KEY": Fernet.generate_key().decode("ascii"),
        }, clear=False)
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.temporary_directory.cleanup()

    @staticmethod
    def _request(cookie_header):
        return Request({
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/api/auth/google/callback",
            "raw_path": b"/api/auth/google/callback",
            "query_string": b"",
            "headers": [(b"cookie", cookie_header.encode())],
            "client": ("127.0.0.1", 1234),
            "server": ("localhost", 8000),
        })

    def _run_google_flow(self, intent, email, role, claims):
        start = auth.google_login_start(intent=intent, email=email, display_name=None, role=role)
        start_cookie = SimpleCookie()
        start_cookie.load(start.headers["set-cookie"])
        state = start_cookie["tea_oauth_state"].value
        claims["nonce"] = self._oauth_nonce()
        request = self._request(f"tea_oauth_state={state}")

        class TokenResponse:
            def raise_for_status(self):
                return None

            @staticmethod
            def json():
                return {"id_token": "test-id-token"}

        with patch.object(auth.requests, "post", return_value=TokenResponse()), patch(
            "google.oauth2.id_token.verify_oauth2_token", return_value=claims
        ):
            return auth.google_login_callback(request, code="authorization-code", state=state)

    def test_super_admin_cannot_bypass_password_and_totp_with_google_login(self):
        with patch.dict(os.environ, {
            "ADMIN_BOOTSTRAP_EMAIL": "admin@example.com",
            "ADMIN_BOOTSTRAP_PASSWORD": "Admin@1234",
        }):
            auth.admin_password_login(
                auth.AdminPasswordRequest(email="admin@example.com", password="Admin@1234")
            )
            response = self._run_google_flow(
                "login",
                "admin@example.com",
                "viewer_buyer",
                {
                    "email": "admin@example.com",
                    "email_verified": True,
                    "name": "Tea Admin",
                },
            )

        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "http://localhost:5173/login?error=super-admin-password")
        self.assertNotIn("tea_session=", response.headers.get("set-cookie", ""))

    def test_google_signup_creates_only_the_selected_self_service_role(self):
        start = auth.google_login_start(intent="signup", email="seller@example.com", display_name=None, role="farmer_seller")
        start_cookie = SimpleCookie()
        start_cookie.load(start.headers["set-cookie"])
        state = start_cookie["tea_oauth_state"].value
        request = self._request(f"tea_oauth_state={state}")

        class TokenResponse:
            def raise_for_status(self):
                return None

            @staticmethod
            def json():
                return {"id_token": "test-id-token"}

        with patch.object(auth.requests, "post", return_value=TokenResponse()), patch(
            "google.oauth2.id_token.verify_oauth2_token",
            return_value={
                "email": "seller@example.com",
                "email_verified": True,
                "name": "Tea Seller",
                "nonce": self._oauth_nonce(),
            },
        ):
            response = auth.google_login_callback(request, code="authorization-code", state=state)

        account = rbac.get_user_by_email("seller@example.com")
        self.assertEqual(account["role"], "farmer_seller")
        self.assertEqual(response.status_code, 303)
        self.assertIn("tea_session=", response.headers["set-cookie"])

    def test_google_staff_signup_requires_approval_before_session_creation(self):
        response = self._run_google_flow(
            "signup",
            "staff@example.com",
            "export_manager",
            {
                "email": "staff@example.com",
                "email_verified": True,
                "name": "Tea Staff",
            },
        )

        account = rbac.get_user_by_email("staff@example.com")
        self.assertEqual(account["approval_status"], "pending")
        self.assertEqual(account["role"], "export_manager")
        self.assertEqual(response.headers["location"], "http://localhost:5173/login?error=pending-approval")
        self.assertNotIn("tea_session=", response.headers.get("set-cookie", ""))

    def test_oauth_state_mismatch_is_rejected(self):
        response = auth.google_login_start(intent="login", email="admin@example.com", display_name=None)
        state_cookie = SimpleCookie()
        state_cookie.load(response.headers["set-cookie"])
        request = self._request(f"tea_oauth_state={state_cookie['tea_oauth_state'].value}")

        from fastapi import HTTPException

        with self.assertRaises(HTTPException) as error:
            auth.google_login_callback(request, code="authorization-code", state="different-state")
        self.assertEqual(error.exception.status_code, 400)

    def _oauth_nonce(self):
        with rbac.connect() as connection:
            row = connection.execute("SELECT nonce FROM oauth_states ORDER BY rowid DESC LIMIT 1").fetchone()
        return row["nonce"]


if __name__ == "__main__":
    unittest.main()
