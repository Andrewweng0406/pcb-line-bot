"""Trusted-operator role assignment; never exposed as a public HTTP route."""
import argparse
import getpass
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import app.core.database as db
from app.core.permissions import ROLE_PERMISSIONS


def set_user_role(email, role, reason):
    if role not in ROLE_PERMISSIONS or not reason.strip() or len(reason) > 1000:
        raise ValueError("Supply a valid role and a non-empty reason of at most 1,000 characters")
    db.init_db()
    with db.SessionLocal() as session:
        user = session.query(db.User).filter(db.User.email == email).first()
        if user is None:
            raise ValueError("User not found")
        if user.role == role:
            return False
        user.role_history = [*(user.role_history or []), {
            "previous_role": user.role, "role": role, "reason": reason.strip(),
            "operator": getpass.getuser(), "source": "operator_cli",
            "at": datetime.now(timezone.utc).isoformat(),
        }]
        user.role = role
        session.commit()
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email")
    parser.add_argument("role", choices=sorted(ROLE_PERMISSIONS))
    parser.add_argument("--reason", required=True)
    args = parser.parse_args()
    changed = set_user_role(args.email, args.role, args.reason)
    print("Role updated and audited" if changed else "Role unchanged")
