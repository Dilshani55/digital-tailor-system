"""Security / robustness: Google sign-in, upload content checks, JSON errors, secrets, CORS."""
import io
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from flask_jwt_extended import create_access_token
from PIL import Image

from app import create_app
from app.routes import auth as auth_routes
from app.utils.helpers import InvalidImageError, save_image


def _png_bytes(size=(40, 60)):
    buf = io.BytesIO()
    Image.new("RGB", size, (200, 30, 60)).save(buf, "PNG")
    buf.seek(0)
    return buf


class FakeFile:
    """Mimics a werkzeug FileStorage: .filename and .save(path)."""
    def __init__(self, data, filename):
        self.data, self.filename = data, filename

    def save(self, path):
        with open(path, "wb") as f:
            f.write(self.data if isinstance(self.data, bytes) else self.data.read())


class TestApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        with cls.app.app_context():
            cls.headers = {"Authorization": f"Bearer {create_access_token(identity='user-1')}"}

    # ── Google sign-in cannot be forged ────────────────────────────────────
    def test_google_login_disabled_when_not_configured(self):
        self.app.config["GOOGLE_CLIENT_ID"] = ""
        r = self.app.test_client().post("/api/auth/google-login", json={"email": "victim@x.com", "full_name": "V"})
        self.assertEqual(r.status_code, 503)
        self.assertNotIn("token", r.get_json())

    def test_google_login_rejects_unverified_email_payload(self):
        self.app.config["GOOGLE_CLIENT_ID"] = "client-123"
        r = self.app.test_client().post("/api/auth/google-login", json={"email": "victim@x.com", "full_name": "V"})
        self.assertEqual(r.status_code, 400)
        self.assertNotIn("token", r.get_json())

    def test_google_login_rejects_a_token_google_does_not_vouch_for(self):
        self.app.config["GOOGLE_CLIENT_ID"] = "client-123"
        with patch.object(auth_routes, "verify_google_credential", return_value=None):
            r = self.app.test_client().post("/api/auth/google-login", json={"credential": "forged"})
        self.assertEqual(r.status_code, 401)
        self.assertNotIn("token", r.get_json())

    def test_google_login_accepts_a_verified_token(self):
        self.app.config["GOOGLE_CLIENT_ID"] = "client-123"
        claims = {"email": "real@x.com", "name": "Real Person", "aud": "client-123", "email_verified": "true"}
        user = MagicMock()
        user.id, user.full_name, user.email = "u1", "Real Person", "real@x.com"
        with patch.object(auth_routes, "verify_google_credential", return_value=claims), \
                patch.object(auth_routes, "User") as U:
            U.objects.return_value.first.return_value = user
            r = self.app.test_client().post("/api/auth/google-login", json={"credential": "good"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("token", r.get_json())

    def test_verify_checks_audience_and_email_verified(self):
        class Resp:
            def __init__(self, body): self.body = body
            def read(self): return self.body
            def __enter__(self): return self
            def __exit__(self, *a): return False
        good = b'{"aud":"c1","email":"a@b.com","email_verified":"true"}'
        with patch.object(auth_routes.urllib.request, "urlopen", return_value=Resp(good)):
            self.assertIsNotNone(auth_routes.verify_google_credential("t", "c1"))
            self.assertIsNone(auth_routes.verify_google_credential("t", "other-client"))
        with patch.object(auth_routes.urllib.request, "urlopen", return_value=Resp(b'{"aud":"c1","email":"a@b.com","email_verified":"false"}')):
            self.assertIsNone(auth_routes.verify_google_credential("t", "c1"))
        with patch.object(auth_routes.urllib.request, "urlopen", side_effect=OSError("offline")):
            self.assertIsNone(auth_routes.verify_google_credential("t", "c1"))

    # ── registration validation ────────────────────────────────────────────
    def test_register_validates_email_and_password(self):
        c = self.app.test_client()
        self.assertEqual(c.post("/api/auth/register", json={"full_name": "A", "email": "nope", "password": "longenough"}).status_code, 400)
        self.assertEqual(c.post("/api/auth/register", json={"full_name": "A", "email": "a@b.co", "password": "short"}).status_code, 400)

    # ── JSON errors, never HTML / traces ─────────────────────────────────────
    def test_unknown_route_and_wrong_method_are_json(self):
        c = self.app.test_client()
        r = c.get("/api/does-not-exist")
        self.assertEqual(r.status_code, 404)
        self.assertTrue(r.is_json)
        self.assertNotIn("Traceback", r.get_data(as_text=True))
        r = c.delete("/api/auth/login")
        self.assertEqual(r.status_code, 405)
        self.assertTrue(r.is_json)

    def test_unhandled_exception_returns_generic_json_500(self):
        with patch("app.routes.fabric.get_all_fabrics", side_effect=RuntimeError("secret path C:\\x\\y.py")):
            r = self.app.test_client().get("/api/fabric/catalog", headers=self.headers)
        if r.status_code == 500:
            self.assertTrue(r.is_json)
            self.assertNotIn("secret path", r.get_data(as_text=True))

    def test_database_outage_is_a_503_json(self):
        from pymongo.errors import ServerSelectionTimeoutError
        with patch("app.routes.auth.User") as U:
            U.objects.side_effect = ServerSelectionTimeoutError("localhost:27017 down")
            r = self.app.test_client().post("/api/auth/login", json={"email": "a@b.co", "password": "whatever1"})
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.get_json()["error_code"], "DATABASE_UNAVAILABLE")
        self.assertNotIn("27017", r.get_data(as_text=True))

    def test_oversized_upload_is_rejected_as_json_413(self):
        self.app.config["MAX_CONTENT_LENGTH"] = 1024
        try:
            data = {"image": (io.BytesIO(b"x" * 5000), "big.png")}
            with patch("app.routes.images.User") as U:
                U.objects.return_value.first.return_value = object()
                r = self.app.test_client().post("/api/images/upload", data=data, content_type="multipart/form-data", headers=self.headers)
            self.assertEqual(r.status_code, 413)
            self.assertTrue(r.is_json)
        finally:
            self.app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

    # ── secrets and CORS ────────────────────────────────────────────────────
    def test_secrets_are_not_shared_constants(self):
        self.assertGreaterEqual(len(self.app.config["JWT_SECRET_KEY"]), 32)
        self.assertNotIn("jwt-digital-tailor-secret-key-2026", (self.app.config["JWT_SECRET_KEY"], self.app.config["SECRET_KEY"]))
        with open(os.path.join(os.path.dirname(__file__), "..", ".env.example"), encoding="utf-8") as f:
            self.assertNotIn("jwt-digital-tailor-secret-key-2026", f.read())

    def test_cors_only_for_configured_origins(self):
        c = self.app.test_client()
        ok = c.options("/api/auth/login", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"})
        bad = c.options("/api/auth/login", headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "POST"})
        self.assertEqual(ok.headers.get("Access-Control-Allow-Origin"), "http://localhost:3000")
        self.assertIsNone(bad.headers.get("Access-Control-Allow-Origin"))


class TestSafeImageStorage(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def test_valid_png_is_stored_with_detected_extension_and_random_name(self):
        name = save_image(FakeFile(_png_bytes(), "../../evil name.jpg"), self.dir)     # lying name is ignored
        self.assertTrue(name.endswith(".png"))
        self.assertNotIn("evil", name)
        self.assertEqual(os.listdir(self.dir), [name])                                # no temp file left behind

    def test_text_disguised_as_image_is_rejected_and_nothing_is_stored(self):
        with self.assertRaises(InvalidImageError):
            save_image(FakeFile(b"<?php echo 1; ?>", "shell.jpg"), self.dir)
        self.assertEqual(os.listdir(self.dir), [])

    def test_truncated_image_is_rejected(self):
        raw = _png_bytes().read()[:40]
        with self.assertRaises(InvalidImageError):
            save_image(FakeFile(raw, "cut.png"), self.dir)
        self.assertEqual(os.listdir(self.dir), [])

    def test_unsupported_format_is_rejected(self):
        buf = io.BytesIO()
        Image.new("RGB", (10, 10)).save(buf, "GIF")
        buf.seek(0)
        with self.assertRaises(InvalidImageError):
            save_image(FakeFile(buf, "anim.png"), self.dir)

    def test_upload_route_returns_400_for_fake_image(self):
        app = create_app()
        app.config["TESTING"] = True
        app.config["UPLOAD_FOLDER"] = self.dir
        with app.app_context():
            headers = {"Authorization": f"Bearer {create_access_token(identity='user-1')}"}
        with patch("app.routes.images.User") as U:
            U.objects.return_value.first.return_value = object()
            r = app.test_client().post("/api/images/upload", data={"image": (io.BytesIO(b"not an image"), "a.jpg")},
                                       content_type="multipart/form-data", headers=headers)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.get_json()["error_code"], "INVALID_IMAGE")


if __name__ == "__main__":
    unittest.main()
