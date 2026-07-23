import json
import sys

sys.path.insert(0, "scripts")

from backup_db import backup  # noqa: E402


def test_backup_writes_all_tables(temp_db, tmp_path):
    from app.core.auth import hash_password

    db_session = temp_db.SessionLocal()
    db_session.add(temp_db.User(email="staff@example.com", password_hash=hash_password("pw")))
    db_session.add(temp_db.Customer(company_name="ABC Corp"))
    db_session.commit()
    db_session.close()

    temp_db.save_quote("line:U1", {"layer": 6, "qty": 1}, {"status": "success", "total": 100.0, "unit_price": 100.0})

    output_path = backup(str(tmp_path))

    with open(output_path) as f:
        snapshot = json.load(f)

    assert len(snapshot["users"]) == 1
    assert snapshot["users"][0]["email"] == "staff@example.com"
    assert len(snapshot["customers"]) == 1
    assert len(snapshot["quote_history"]) == 1
    assert snapshot["quote_history"][0]["total"] == 100.0
