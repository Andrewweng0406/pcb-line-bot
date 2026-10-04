import sys

sys.path.insert(0, "scripts")

from create_user import create_user  # noqa: E402


def test_create_user_inserts_row(temp_db):
    create_user("owner@example.com", "hunter2")

    db = temp_db.SessionLocal()
    user = db.query(temp_db.User).filter(temp_db.User.email == "owner@example.com").first()
    assert user is not None
    assert user.password_hash != "hunter2"
    assert user.role == "staff"
    db.close()


def test_role_provisioning_does_not_escalate_an_existing_account(temp_db):
    create_user("admin@example.com", "test-password", role="admin")
    create_user("staff@example.com", "test-password")
    create_user("staff@example.com", "other-password", role="admin")
    with temp_db.SessionLocal() as session:
        assert session.query(temp_db.User).filter_by(email="admin@example.com").one().role == "admin"
        assert session.query(temp_db.User).filter_by(email="staff@example.com").one().role == "staff"


def test_create_user_is_idempotent(temp_db):
    create_user("owner@example.com", "hunter2")
    create_user("owner@example.com", "hunter2")

    db = temp_db.SessionLocal()
    count = db.query(temp_db.User).filter(temp_db.User.email == "owner@example.com").count()
    assert count == 1
    db.close()
