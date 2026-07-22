"""CLI to create a web login account.

Usage: python scripts/create_user.py <email> <password>
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import app.core.database as db  # noqa: E402
from app.core.auth import hash_password  # noqa: E402


def create_user(email: str, password: str) -> None:
    # Accessed as module attributes (not `from ... import X`) so this keeps
    # working correctly under tests that reload app.core.database against a
    # temporary database.
    db.init_db()
    session = db.SessionLocal()
    try:
        existing = session.query(db.User).filter(db.User.email == email).first()
        if existing:
            print(f"User already exists: {email}")
            return
        user = db.User(email=email, password_hash=hash_password(password))
        session.add(user)
        session.commit()
        print(f"Created user: {email}")
    finally:
        session.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python scripts/create_user.py <email> <password>")
        sys.exit(1)
    create_user(sys.argv[1], sys.argv[2])
