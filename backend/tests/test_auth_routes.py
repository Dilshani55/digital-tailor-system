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
            self.assertEqual(self.c.get(path).status_code, 401, path)
            self.assertEqual(self.c.get(path, headers={"Authorization": "Bearer not.a.token"}).status_code, 422, path)

    def test_expired_token_is_rejected(self):
        from datetime import timedelta
        with self.app.app_context():
            token = create_access_token(identity="u1", expires_delta=timedelta(seconds=-5))
        r = self.c.get("/api/auth/profile", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(r.status_code, 401)

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
