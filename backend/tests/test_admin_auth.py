import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cryptography.fernet import Fernet
from fastapi import HTTPException, Response

from app.api import auth
from app.core import rbac


class SuperAdminAuthTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "rbac.sqlite3"
        self.environment = patch.dict(os.environ, {
            "RBAC_DATABASE_PATH": str(self.database_path),
            "ADMIN_BOOTSTRAP_EMAIL": "admin@gmail.com",
            "ADMIN_BOOTSTRAP_PASSWORD": "Admin@1234",
            "TOTP_ENCRYPTION_KEY": Fernet.generate_key().decode("ascii"),
        }, clear=False)
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.temporary_directory.cleanup()

    def test_super_admin_enrolls_authenticator_and_uses_it_for_later_logins(self):
        enrollment = auth.admin_password_login(
            auth.AdminPasswordRequest(email="admin@gmail.com", password="Admin@1234")
        )
        self.assertTrue(enrollment["setup_required"])
        self.assertTrue(enrollment["qr_code"].startswith("data:image/png;base64,"))

        super_admin = rbac.get_user_by_email("admin@gmail.com")
        self.assertTrue(super_admin["is_super_admin"])
        self.assertIsNone(super_admin["totp_secret_encrypted"])
        self.assertTrue(super_admin["password_hash"].startswith("scrypt$"))

        wrong_code = next(
            f"{candidate:06d}"
            for candidate in range(1_000_000)
            if not auth._verify_totp(enrollment["manual_entry_key"], f"{candidate:06d}")
        )
        with self.assertRaises(HTTPException):
            auth.admin_totp_verify(
                auth.TotpVerifyRequest(challenge_id=enrollment["challenge_id"], code=wrong_code),
                Response(),
            )
        with rbac.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM admin_auth_challenges").fetchone()[0], 1)

        enrolled_response = Response()
        result = auth.admin_totp_verify(
            auth.TotpVerifyRequest(
                challenge_id=enrollment["challenge_id"],
                code=auth._totp_code(enrollment["manual_entry_key"]),
            ),
            enrolled_response,
        )
        self.assertTrue(result["authenticated"])
        self.assertIn("tea_session=", enrolled_response.headers["set-cookie"])

        super_admin = rbac.get_user_by_email("admin@gmail.com")
        self.assertTrue(super_admin["totp_enabled"])
        self.assertNotEqual(super_admin["totp_secret_encrypted"], enrollment["manual_entry_key"])

        login = auth.admin_password_login(
            auth.AdminPasswordRequest(email="admin@gmail.com", password="Admin@1234")
        )
        self.assertFalse(login["setup_required"])
        login_response = Response()
        auth.admin_totp_verify(
            auth.TotpVerifyRequest(
                challenge_id=login["challenge_id"],
                code=auth._totp_code(auth._decrypt_totp_secret(super_admin["totp_secret_encrypted"])),
            ),
            login_response,
        )
        self.assertIn("tea_session=", login_response.headers["set-cookie"])

    def test_super_admin_cannot_be_deactivated(self):
        auth.admin_password_login(
            auth.AdminPasswordRequest(email="admin@gmail.com", password="Admin@1234")
        )
        super_admin = dict(rbac.get_user_by_email("admin@gmail.com"))
        with self.assertRaises(HTTPException) as error:
            auth.update_user(
                super_admin["id"],
                auth.UserUpdateRequest(active=False),
                super_admin,
            )
        self.assertEqual(error.exception.status_code, 409)
        self.assertTrue(rbac.get_user_by_email("admin@gmail.com")["active"])

    def test_bootstrap_password_is_not_required_after_super_admin_exists(self):
        auth.admin_password_login(
            auth.AdminPasswordRequest(email="admin@gmail.com", password="Admin@1234")
        )
        with patch.dict(os.environ, {"ADMIN_BOOTSTRAP_PASSWORD": ""}):
            later_login = auth.admin_password_login(
                auth.AdminPasswordRequest(email="admin@gmail.com", password="Admin@1234")
            )
        self.assertTrue(later_login["setup_required"])

    def test_role_requests_require_admin_approval_and_admin_role_requires_super_admin(self):
        now = rbac.iso_time()
        with rbac.connect() as connection:
            staff_cursor = connection.execute(
                """INSERT INTO users (email, display_name, role, approval_status, created_at, updated_at)
                   VALUES ('staff@example.com', 'Staff', 'export_manager', 'pending', ?, ?)""",
                (now, now),
            )
            admin_cursor = connection.execute(
                """INSERT INTO users (email, display_name, role, approval_status, created_at, updated_at)
                   VALUES ('applicant@example.com', 'Applicant', 'admin', 'pending', ?, ?)""",
                (now, now),
            )
            standard_admin_cursor = connection.execute(
                """INSERT INTO users (email, display_name, role, created_at, updated_at)
                   VALUES ('manager@example.com', 'Manager', 'admin', ?, ?)""",
                (now, now),
            )

        standard_admin = dict(rbac.get_user_by_id(standard_admin_cursor.lastrowid))
        staff_id = staff_cursor.lastrowid
        applicant_id = admin_cursor.lastrowid
        auth.decide_user_request(staff_id, auth.ApprovalRequest(status="approved"), standard_admin)
        self.assertEqual(rbac.get_user_by_id(staff_id)["approval_status"], "approved")

        with self.assertRaises(HTTPException) as error:
            auth.decide_user_request(
                applicant_id,
                auth.ApprovalRequest(status="approved"),
                standard_admin,
            )
        self.assertEqual(error.exception.status_code, 403)
        self.assertEqual(rbac.get_user_by_id(applicant_id)["approval_status"], "pending")

        super_admin = auth.admin_password_login(
            auth.AdminPasswordRequest(email="admin@gmail.com", password="Admin@1234")
        )
        self.assertTrue(super_admin["setup_required"])
        super_admin_user = dict(rbac.get_user_by_email("admin@gmail.com"))
        auth.decide_user_request(
            applicant_id,
            auth.ApprovalRequest(status="approved"),
            super_admin_user,
        )
        self.assertEqual(rbac.get_user_by_id(applicant_id)["approval_status"], "approved")


if __name__ == "__main__":
    unittest.main()
