"""Authentication routes: register, login, profile, token protection (database mocked)."""
import unittest
from unittest.mock import MagicMock, patch

import bcrypt
from flask_jwt_extended import create_access_token

from app import create_app


def _user(email="alice@example.com", password="correct-horse-1", uid="64d0a1b2c3d4e5f601234567"):
    u = MagicMock()
    u.id = uid
    u.full_name = "Alice"
    u.email = email
    u.password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    u.created_at = "2026-01-01"
    return u


class TestAuthRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.c = cls.app.test_client()

    def test_register_creates_a_user_with_a_hashed_lower_case_email(self):
        saved = {}

        class FakeUser:
            objects = MagicMock(return_value=MagicMock(first=MagicMock(return_value=None)))

            def __init__(self, **kw):
                saved.update(kw)
                self.id, self.full_name, self.email = "u1", kw["full_name"], kw["email"]

            def save(self):
                pass

        with patch("app.routes.auth.User", FakeUser):
            r = self.c.post("/api/auth/register", json={"full_name": " Alice ", "email": "Alice@Example.COM", "password": "correct-horse-1"})
        self.assertEqual(r.status_code, 201, r.get_json())
        self.assertEqual(saved["email"], "alice@example.com")
        self.assertEqual(saved["full_name"], "Alice")
        self.assertNotEqual(saved["password"], "correct-horse-1")
        self.assertTrue(bcrypt.checkpw(b"correct-horse-1", saved["password"].encode()))

    def test_register_rejects_duplicates_and_missing_fields(self):
        with patch("app.routes.auth.User") as U:
            U.objects.return_value.first.return_value = _user()
            r = self.c.post("/api/auth/register", json={"full_name": "A", "email": "alice@example.com", "password": "correct-horse-1"})
        self.assertEqual(r.status_code, 409)
        self.assertEqual(self.c.post("/api/auth/register", json={"email": "a@b.co", "password": "longenough"}).status_code, 400)

    def test_login_success_returns_a_working_token(self):
        with patch("app.routes.auth.User") as U:
            u = _user()
            U.objects.return_value.first.return_value = u
            r = self.c.post("/api/auth/login", json={"email": "ALICE@example.com", "password": "correct-horse-1"})
            body = r.get_json()
            self.assertEqual(r.status_code, 200)
            self.assertNotIn("password", str(body["user"]))
            prof = self.c.get("/api/auth/profile", headers={"Authorization": f"Bearer {body['token']}"})
        self.assertEqual(prof.status_code, 200)
        self.assertEqual(prof.get_json()["email"], "alice@example.com")

    def test_login_rejects_wrong_password_and_unknown_user_identically(self):
        with patch("app.routes.auth.User") as U:
            U.objects.return_value.first.return_value = _user()
            wrong = self.c.post("/api/auth/login", json={"email": "alice@example.com", "password": "nope-nope-1"})
            U.objects.return_value.first.return_value = None
            unknown = self.c.post("/api/auth/login", json={"email": "who@example.com", "password": "nope-nope-1"})
        self.assertEqual(wrong.status_code, 401)
        self.assertEqual(unknown.status_code, 401)
        self.assertEqual(wrong.get_json()["error"], unknown.get_json()["error"])     # no user enumeration

    def test_login_requires_both_fields(self):
        self.assertEqual(self.c.post("/api/auth/login", json={"email": "a@b.co"}).status_code, 400)
        self.assertEqual(self.c.post("/api/auth/login", json={}).status_code, 400)

    def test_protected_routes_reject_missing_and_bad_tokens(self):
        for path in ("/api/auth/profile", "/api/patterns/", "/api/measurements/", "/api/images/", "/api/export/",
                     "/api/research/metrics"):
            missing = self.c.get(path)
            self.assertEqual((missing.status_code, missing.get_json()["error_code"]), (401, "AUTHORIZATION_REQUIRED"), path)
            bad = self.c.get(path, headers={"Authorization": "Bearer not.a.token"})
            self.assertEqual((bad.status_code, bad.get_json()["error_code"]), (401, "INVALID_TOKEN"), path)

    def test_expired_token_is_rejected(self):
        from datetime import timedelta
        with self.app.app_context():
            token = create_access_token(identity="u1", expires_delta=timedelta(seconds=-5))
        r = self.c.get("/api/auth/profile", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.get_json()["error_code"], "TOKEN_EXPIRED")

    # ── the signing key ──────────────────────────────────────────────────────
    def test_a_token_stays_valid_across_a_restart_when_the_key_is_fixed(self):
        """Two app instances (before / after a restart) with the same key, as backend/.env provides."""
        key = "k" * 48
        before, after = create_app(), create_app()
        before.config["JWT_SECRET_KEY"] = after.config["JWT_SECRET_KEY"] = key
        with before.app_context():
            token = create_access_token(identity="64d0a1b2c3d4e5f601234567")
        with patch("app.routes.auth.User") as U:
            U.objects.return_value.first.return_value = _user()
            r = after.test_client().get("/api/auth/profile", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(r.status_code, 200)

    def test_a_token_signed_with_another_key_is_a_401_that_signs_the_user_out(self):
        other = create_app()
        other.config["JWT_SECRET_KEY"] = "another-key-" + "x" * 40
        with other.app_context():
            token = create_access_token(identity="64d0a1b2c3d4e5f601234567")
        r = self.c.get("/api/auth/profile", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual((r.status_code, r.get_json()["error_code"]), (401, "INVALID_TOKEN"))
        self.assertNotIn("Signature", r.get_data(as_text=True))                  # no internals in the message

    def test_a_tampered_token_is_rejected(self):
        import base64
        import json as _json
        with self.app.app_context():
            token = create_access_token(identity="alice")
        head, payload, sig = token.split(".")
        body = _json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        body["sub"] = "mallory"
        forged = base64.urlsafe_b64encode(_json.dumps(body).encode()).decode().rstrip("=")
        r = self.c.get("/api/auth/profile", headers={"Authorization": f"Bearer {head}.{forged}.{sig}"})
        self.assertEqual(r.status_code, 401)

    def test_the_configured_key_is_long_and_never_returned_by_the_api(self):
        key = self.app.config["JWT_SECRET_KEY"]
        self.assertGreaterEqual(len(key), 32)
        for path in ("/", "/api/images/model-status", "/api/does-not-exist"):
            self.assertNotIn(key, self.c.get(path).get_data(as_text=True))

    # ── change password ──────────────────────────────────────────────────────
    def _change(self, user, body, token_for="64d0a1b2c3d4e5f601234567"):
        with self.app.app_context():
            token = create_access_token(identity=token_for)
        with patch("app.routes.auth.User") as U:
            U.objects.return_value.first.return_value = user
            return self.c.post("/api/auth/change-password", json=body, headers={"Authorization": f"Bearer {token}"})

    def test_change_password_needs_the_current_password_and_stores_only_a_hash(self):
        u = _user()
        r = self._change(u, {"current_password": "correct-horse-1", "new_password": "new-battery-9"})
        self.assertEqual(r.status_code, 200, r.get_json())
        u.save.assert_called_once()
        self.assertNotIn("new-battery-9", u.password)
        self.assertTrue(bcrypt.checkpw(b"new-battery-9", u.password.encode()))
        self.assertFalse(bcrypt.checkpw(b"correct-horse-1", u.password.encode()))
        self.assertNotIn("new-battery-9", r.get_data(as_text=True))

    def test_change_password_refusals_change_nothing(self):
        cases = [
            ({"current_password": "wrong-wrong-1", "new_password": "new-battery-9"}, "CURRENT_PASSWORD_WRONG"),
            ({"current_password": "correct-horse-1", "new_password": "short"}, "PASSWORD_TOO_SHORT"),
            ({"current_password": "correct-horse-1", "new_password": "correct-horse-1"}, "PASSWORD_UNCHANGED"),
            ({"current_password": "correct-horse-1", "new_password": "x" * 80}, "PASSWORD_TOO_LONG"),
            ({"new_password": "new-battery-9"}, "PASSWORD_FIELDS_REQUIRED"),
            ({"current_password": 12345678, "new_password": "new-battery-9"}, "PASSWORD_FIELDS_REQUIRED"),
        ]
        for body, code in cases:
            u = _user()
            old = u.password
            r = self._change(u, body)
            self.assertEqual((r.status_code, r.get_json()["error_code"]), (400, code), body)   # 400, never 401: not a session problem
            self.assertEqual(u.password, old)
            u.save.assert_not_called()

    def test_change_password_requires_sign_in(self):
        r = self.c.post("/api/auth/change-password", json={"current_password": "a", "new_password": "new-battery-9"})
        self.assertEqual(r.status_code, 401)

    def test_operator_reset_tool_sets_a_hash_and_refuses_unknown_accounts_and_short_passwords(self):
        import importlib.util
        import os
        spec = importlib.util.spec_from_file_location(
            "reset_password", os.path.join(os.path.dirname(__file__), "..", "tools", "reset_password.py"))
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        u = _user()
        with patch.object(tool, "User") as U:
            U.objects.return_value.first.return_value = u
            ok, message = tool.set_password("Alice@Example.com", "operator-set-7")
            self.assertTrue(ok)
            self.assertNotIn("operator-set-7", message)
            self.assertTrue(bcrypt.checkpw(b"operator-set-7", u.password.encode()))
            self.assertFalse(tool.set_password("alice@example.com", "short")[0])
            U.objects.return_value.first.return_value = None
            self.assertFalse(tool.set_password("nobody@example.com", "operator-set-7")[0])

    def test_a_user_cannot_read_someone_elses_pattern(self):
        with self.app.app_context():
            token = create_access_token(identity="mallory")
        pat = MagicMock()
        pat.session_id.user_id.id = "alice"
        with patch("app.routes.patterns.PatternResult") as PR:
            PR.objects.return_value.first.return_value = pat
            r = self.c.get("/api/patterns/abc", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(r.status_code, 403)


if __name__ == "__main__":
    unittest.main()
