import sys

sys.path.insert(0, "scripts")

from create_user import create_user  # noqa: E402


def test_create_user_inserts_row(temp_db):
    create_user("owner@example.com", "hunter2")

    db = temp_db.SessionLocal()
    user = db.query(temp_db.User).filter(temp_db.User.email == "owner@example.com").first()
    assert user is not None
    assert user.password_hash != "hunter2"
    db.close()


def test_create_user_is_idempotent(temp_db):
    create_user("owner@example.com", "hunter2")
    create_user("owner@example.com", "hunter2")

    db = temp_db.SessionLocal()
    count = db.query(temp_db.User).filter(temp_db.User.email == "owner@example.com").count()
    assert count == 1
    db.close()
