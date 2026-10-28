import os
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from cryptography.fernet import Fernet
from fastapi import HTTPException, Response

from app.api import auth
from app.core import rbac


class SuperAdminInviteTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "rbac.sqlite3"
        self.environment = patch.dict(os.environ, {
            "RBAC_DATABASE_PATH": str(self.database_path),
            "ADMIN_BOOTSTRAP_EMAIL": "admin@example.com",
            "ADMIN_BOOTSTRAP_PASSWORD": "Bootstrap@1234",
            "TOTP_ENCRYPTION_KEY": Fernet.generate_key().decode("ascii"),
        }, clear=False)
        self.environment.start()
        auth.admin_password_login(
            auth.AdminPasswordRequest(email="admin@example.com", password="Bootstrap@1234")
        )
        self.super_admin = dict(rbac.get_user_by_email("admin@example.com"))

    def tearDown(self):
        self.environment.stop()
        self.temporary_directory.cleanup()

    def test_invitation_creates_hashed_one_time_token_and_new_super_admin_enrolls_totp(self):
        invitation = auth.create_super_admin_invite(
            auth.SuperAdminInviteRequest(email="new-admin@example.com", display_name="New Admin"),
            self.super_admin,
        )
        with rbac.connect() as connection:
            stored = connection.execute("SELECT * FROM super_admin_invites").fetchone()
        self.assertEqual(stored["token_hash"], rbac.digest(invitation["invite_token"]))
        self.assertNotEqual(stored["token_hash"], invitation["invite_token"])

        result = auth.accept_super_admin_invite(
            auth.SuperAdminInviteAcceptRequest(
                invite_token=invitation["invite_token"],
                password="A-secure-new-password",
            )
        )
        self.assertEqual(result["email"], "new-admin@example.com")
        invited_admin = dict(rbac.get_user_by_email("new-admin@example.com"))
        self.assertTrue(invited_admin["is_super_admin"])
        self.assertEqual(invited_admin["role"], "admin")
        self.assertTrue(auth._verify_password("A-secure-new-password", invited_admin["password_hash"]))
        self.assertFalse(invited_admin["totp_enabled"])

        challenge = auth.admin_password_login(
            auth.AdminPasswordRequest(email="new-admin@example.com", password="A-secure-new-password")
        )
        self.assertTrue(challenge["setup_required"])
        verify_response = Response()
        auth.admin_totp_verify(
            auth.TotpVerifyRequest(
                challenge_id=challenge["challenge_id"],
                code=auth._totp_code(challenge["manual_entry_key"]),
            ),
            verify_response,
        )
        self.assertTrue(rbac.get_user_by_email("new-admin@example.com")["totp_enabled"])

        with self.assertRaises(HTTPException) as error:
            auth.accept_super_admin_invite(
                auth.SuperAdminInviteAcceptRequest(
                    invite_token=invitation["invite_token"],
                    password="A-secure-new-password",
                )
            )
        self.assertEqual(error.exception.status_code, 400)

    def test_only_super_admin_can_create_an_invitation(self):
        now = rbac.iso_time()
        with rbac.connect() as connection:
            cursor = connection.execute(
                """INSERT INTO users (email, display_name, role, created_at, updated_at)
                   VALUES ('manager@example.com', 'Manager', 'admin', ?, ?) RETURNING id""",
                (now, now),
            )
            standard_admin_id = cursor.fetchone()["id"]
        standard_admin = dict(rbac.get_user_by_id(standard_admin_id))

        with self.assertRaises(HTTPException) as error:
            auth.create_super_admin_invite(
                auth.SuperAdminInviteRequest(email="new-admin@example.com", display_name="New Admin"),
                standard_admin,
            )
        self.assertEqual(error.exception.status_code, 403)

    def test_duplicate_accounts_are_rejected_and_reissued_invites_invalidate_the_old_link(self):
        with self.assertRaises(HTTPException) as existing_error:
            auth.create_super_admin_invite(
                auth.SuperAdminInviteRequest(email="admin@example.com", display_name="Duplicate"),
                self.super_admin,
            )
        self.assertEqual(existing_error.exception.status_code, 409)

        first_invitation = auth.create_super_admin_invite(
            auth.SuperAdminInviteRequest(email="new-admin@example.com", display_name="New Admin"),
            self.super_admin,
        )
        replacement = auth.create_super_admin_invite(
            auth.SuperAdminInviteRequest(email="NEW-ADMIN@example.com", display_name="New Admin"),
            self.super_admin,
        )
        self.assertNotEqual(first_invitation["invite_token"], replacement["invite_token"])
        with rbac.connect() as connection:
            invites = connection.execute("SELECT token_hash FROM super_admin_invites").fetchall()
        self.assertEqual(len(invites), 1)
        self.assertEqual(invites[0]["token_hash"], rbac.digest(replacement["invite_token"]))
        with self.assertRaises(HTTPException) as old_invite_error:
            auth.accept_super_admin_invite(
                auth.SuperAdminInviteAcceptRequest(
                    invite_token=first_invitation["invite_token"],
                    password="A-secure-new-password",
                )
            )
        self.assertEqual(old_invite_error.exception.status_code, 400)

    def test_expired_invitation_cannot_be_accepted(self):
        invitation = auth.create_super_admin_invite(
            auth.SuperAdminInviteRequest(email="expired@example.com", display_name="Expired"),
            self.super_admin,
        )
        with rbac.connect() as connection:
            connection.execute(
                "UPDATE super_admin_invites SET expires_at = ? WHERE token_hash = ?",
                (rbac.iso_time(rbac.utc_now() - timedelta(seconds=1)), rbac.digest(invitation["invite_token"])),
            )

        with self.assertRaises(HTTPException) as error:
            auth.accept_super_admin_invite(
                auth.SuperAdminInviteAcceptRequest(
                    invite_token=invitation["invite_token"],
                    password="A-secure-new-password",
                )
            )
        self.assertEqual(error.exception.status_code, 400)
        self.assertIsNone(rbac.get_user_by_email("expired@example.com"))
        with rbac.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM super_admin_invites").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
