import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from starlette.requests import Request


class RbacPermissionTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "rbac.sqlite3"
        self.environment = patch.dict(os.environ, {"RBAC_DATABASE_PATH": str(self.database_path)})
        self.environment.start()
        from app.core import rbac

        self.rbac = rbac
        with rbac.connect() as connection:
            for email, name, role in (
                ("admin@example.com", "Admin", "admin"),
                ("buyer@example.com", "Buyer", "viewer_buyer"),
                ("seller@example.com", "Seller", "farmer_seller"),
            ):
                connection.execute(
                    """INSERT INTO users (email, display_name, role, active, created_at, updated_at)
                       VALUES (?, ?, ?, 1, ?, ?)""",
                    (email, name, role, rbac.iso_time(), rbac.iso_time()),
                )
            connection.execute(
                "INSERT INTO users (email, display_name, role, active, created_at, updated_at) VALUES (?, ?, ?, 0, ?, ?)",
                ("disabled@example.com", "Disabled", "viewer_buyer", rbac.iso_time(), rbac.iso_time()),
            )

    def tearDown(self):
        self.environment.stop()
        self.temporary_directory.cleanup()

    def _request(self, method="GET", cookies=None):
        headers = []
        if cookies:
            headers.append((b"cookie", "; ".join(f"{name}={value}" for name, value in cookies.items()).encode()))
        return Request({
            "type": "http",
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "headers": headers,
            "client": ("127.0.0.1", 1234),
            "server": ("testserver", 80),
        })

    def _user_id(self, email):
        return self.rbac.get_user_by_email(email)["id"]

    def test_buyer_can_view_reports_but_cannot_manage_users(self):
        token, _ = self.rbac.create_session(self._user_id("buyer@example.com"))
        request = self._request(cookies={self.rbac.SESSION_COOKIE: token})

        user = self.rbac.require_permission("reports:view")(request)
        self.assertEqual(user["role"], "viewer_buyer")
        with self.assertRaises(HTTPException) as error:
            self.rbac.require_permission("users:manage")(request)
        self.assertEqual(error.exception.status_code, 403)

    def test_unauthenticated_user_is_rejected(self):
        with self.assertRaises(HTTPException) as error:
            self.rbac.require_permission("forecast:view")(self._request())
        self.assertEqual(error.exception.status_code, 401)

    def test_deactivated_user_session_is_rejected(self):
        token, _ = self.rbac.create_session(self._user_id("disabled@example.com"))
        with self.assertRaises(HTTPException) as error:
            self.rbac.require_permission("home:view")(
                self._request(cookies={self.rbac.SESSION_COOKIE: token})
            )
        self.assertEqual(error.exception.status_code, 401)

    def test_seller_can_only_list_owned_passport_data(self):
        seller_id = self._user_id("seller@example.com")
        owned = self.rbac.ensure_passport_batch("SELLER-1", seller_id)
        other = self.rbac.ensure_passport_batch("SELLER-2", self._user_id("admin@example.com"))

        self.assertEqual(self.rbac.get_passport_batch(owned["batch_id"])["owner_user_id"], seller_id)
        self.assertNotEqual(owned["public_id"], other["public_id"])
        self.assertIsNone(self.rbac.get_public_batch("unknown-public-id"))

    def test_role_permissions_follow_role_policy(self):
        self.assertTrue(self.rbac.role_has_permission("admin", "users:manage"))
        self.assertFalse(self.rbac.role_has_permission("viewer_buyer", "users:manage"))
        self.assertFalse(self.rbac.role_has_permission("farmer_seller", "market:view"))


if __name__ == "__main__":
    unittest.main()
