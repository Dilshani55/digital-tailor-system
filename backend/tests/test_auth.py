import unittest
import sys
import os

# Adjust path to import app modules correctly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.models.user import User
import bcrypt

class TestAuth(unittest.TestCase):
    def test_password_hashing(self):
        """Verify that password hashing and verification works using bcrypt."""
        password = "secure_password_123"
        
        # Hash password
        hashed = bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt()
        ).decode("utf-8")
        
        self.assertNotEqual(password, hashed)
        
        # Verify matching password
        match = bcrypt.checkpw(
            password.encode("utf-8"),
            hashed.encode("utf-8")
        )
        self.assertTrue(match)

        # Verify mismatched password
        mismatch = bcrypt.checkpw(
            "wrong_password".encode("utf-8"),
            hashed.encode("utf-8")
        )
        self.assertFalse(mismatch)

    def test_user_model_instantiation(self):
        """Test User schema validation attributes."""
        user = User(
            full_name="Dilshani Vitharana",
            email="dilshani@example.com",
            password="hashedpassword123"
        )
        self.assertEqual(user.full_name, "Dilshani Vitharana")
        self.assertEqual(user.email, "dilshani@example.com")
        self.assertEqual(user.password, "hashedpassword123")

if __name__ == '__main__':
    unittest.main()
