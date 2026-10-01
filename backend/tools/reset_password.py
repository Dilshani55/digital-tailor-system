#!/usr/bin/env python3
"""
reset_password.py - set a new password for an account, run by the person who operates the server.

The app has no "forgot password" e-mail because it has no e-mail service. A user who can still sign in changes
the password under Settings. A user who cannot asks the operator, who checks who is asking and then runs:

    cd backend
    venv\\Scripts\\python tools\\reset_password.py --email user@example.com

The new password is typed twice and never shown or stored anywhere except as a bcrypt hash in the database.
The database is the one configured in backend/.env (MONGO_URI). Nothing else is changed.
"""

import argparse
import getpass
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import bcrypt                                                                   # noqa: E402
from mongoengine import connect                                                 # noqa: E402

from config import Config                                                       # noqa: E402
from app.models.user import User                                                # noqa: E402

MIN_LENGTH = 8


def set_password(email, new_password):
    """Returns (ok, message). Finds the account case-insensitively, as sign-in does."""
    email = (email or "").strip()
    user = User.objects(email=email.lower()).first() or User.objects(email=email).first()
    if not user:
        return False, f"No account with the e-mail '{email}'."
    if len(new_password) < MIN_LENGTH:
        return False, f"The password must be at least {MIN_LENGTH} characters."
    if len(new_password.encode("utf-8")) > 72:
        return False, "The password is too long (72 bytes at most)."
    user.password = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    user.save()
    return True, f"Password changed for {user.email}."


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--email", required=True)
    a = ap.parse_args()
    connect(host=Config.MONGO_URI, serverSelectionTimeoutMS=5000)
    first = getpass.getpass("New password: ")
    if first != getpass.getpass("New password again: "):
        sys.exit("The two passwords are not the same. Nothing was changed.")
    ok, message = set_password(a.email, first)
    print(message)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
