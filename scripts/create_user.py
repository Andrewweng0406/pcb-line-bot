"""CLI to create a web login account.

Usage: python scripts/create_user.py <email> <password>
"""
import os
import sys
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import app.core.database as db  # noqa: E402
from app.core.auth import hash_password  # noqa: E402
from app.core.permissions import ROLE_PERMISSIONS  # noqa: E402


def create_user(email: str, password: str, role: str = "staff") -> None:
    # Accessed as module attributes (not `from ... import X`) so this keeps
    # working correctly under tests that reload app.core.database against a
    # temporary database.
    if role not in ROLE_PERMISSIONS:
        raise ValueError("Invalid role")
    db.init_db()
    session = db.SessionLocal()
    try:
        existing = session.query(db.User).filter(db.User.email == email).first()
        if existing:
            print(f"User already exists: {email}")
            return
        user = db.User(email=email, password_hash=hash_password(password), role=role)
        session.add(user)
        session.commit()
        print(f"Created user: {email}")
    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a staff account without modifying existing accounts")
    parser.add_argument("email")
    parser.add_argument("password")
    parser.add_argument("--role", choices=sorted(ROLE_PERMISSIONS), default="staff")
    args = parser.parse_args()
    create_user(args.email, args.password, args.role)
