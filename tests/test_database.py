from app.core.auth import hash_password


def test_create_user(temp_db):
    db = temp_db.SessionLocal()
    user = temp_db.User(email="staff@example.com", password_hash=hash_password("pw"))
    db.add(user)
    db.commit()
    db.refresh(user)
    assert user.id is not None
    db.close()


def test_create_customer(temp_db):
    db = temp_db.SessionLocal()
    customer = temp_db.Customer(company_name="ABC Corp", contact="Jane")
    db.add(customer)
    db.commit()
    db.refresh(customer)
    assert customer.id is not None
    db.close()


def test_save_quote_stores_full_spec_and_breakdown(temp_db):
    parsed = {"layer": 6, "material": "FR4", "qty": 9, "enig": True}
    result = {"status": "success", "total": 12345.0, "unit_price": 1371.67, "issue_ratio": 1.0}

    ok = temp_db.save_quote("line:U123", parsed, result)
    assert ok is True

    db = temp_db.SessionLocal()
    quote = db.query(temp_db.QuoteHistory).order_by(temp_db.QuoteHistory.id.desc()).first()
    assert quote.source_channel_id == "line:U123"
    assert quote.total == 12345.0
    assert quote.status == "pending"
    assert quote.spec_json == parsed
    assert quote.breakdown_json == result
    assert quote.quote_no.startswith("PCB-")
    db.close()


def test_save_quote_links_customer_and_creator(temp_db):
    db = temp_db.SessionLocal()
    user = temp_db.User(email="staff@example.com", password_hash="x")
    customer = temp_db.Customer(company_name="ABC Corp")
    db.add_all([user, customer])
    db.commit()
    db.refresh(user)
    db.refresh(customer)
    db.close()

    parsed = {"layer": 4, "qty": 2}
    result = {"status": "success", "total": 5000.0, "unit_price": 2500.0, "issue_ratio": 1.0}
    temp_db.save_quote(
        "web:1", parsed, result, customer_id=customer.id, created_by_user_id=user.id
    )

    db = temp_db.SessionLocal()
    quote = db.query(temp_db.QuoteHistory).order_by(temp_db.QuoteHistory.id.desc()).first()
    assert quote.customer_id == customer.id
    assert quote.created_by_user_id == user.id
    assert quote.customer.company_name == "ABC Corp"
    db.close()


def test_migration_adds_expected_columns(temp_db):
    """A fresh DB is created directly with the current schema by create_all(),
    so this just confirms the new columns exist end to end (the rename path
    is only exercised against a pre-existing legacy DB, which is what
    _run_migrations's early-return-on-fresh-db branch guards against).
    """
    from sqlalchemy import inspect

    inspector = inspect(temp_db.engine)
    columns = {col["name"] for col in inspector.get_columns("quote_history")}
    assert "source_channel_id" in columns
    assert "customer_id" in columns
    assert "spec_json" in columns
    assert "breakdown_json" in columns
    assert "created_by_user_id" in columns
    assert "updated_by_user_id" in columns


def test_migration_upgrades_legacy_schema_without_losing_data(temp_db):
    """Simulate a pre-migration database: a `quote_history` table with only
    the old String `customer_id` column (holding a LINE user_id) and none of
    the new columns. Running the migration must rename that column to
    `source_channel_id`, preserve its data, and add the new columns.
    """
    from sqlalchemy import inspect, text

    with temp_db.engine.begin() as conn:
        conn.execute(text("DROP TABLE quote_history"))
        conn.execute(text(
            """
            CREATE TABLE quote_history (
                id INTEGER PRIMARY KEY,
                customer_id VARCHAR(255),
                layer INTEGER,
                material VARCHAR(100),
                length_mm FLOAT,
                width_mm FLOAT,
                qty INTEGER,
                issue_ratio FLOAT,
                total FLOAT,
                unit_price FLOAT,
                created_at DATETIME
            )
            """
        ))
        conn.execute(text(
            "INSERT INTO quote_history (customer_id, layer, total) "
            "VALUES ('Uabc123', 6, 12345.0)"
        ))

    temp_db._run_migrations(temp_db.engine)

    inspector = inspect(temp_db.engine)
    columns = {col["name"] for col in inspector.get_columns("quote_history")}
    assert "source_channel_id" in columns
    assert "spec_json" in columns

    db = temp_db.SessionLocal()
    quote = db.query(temp_db.QuoteHistory).first()
    assert quote.source_channel_id == "Uabc123"
    assert quote.total == 12345.0
    db.close()


def test_get_stats_by_layer_groups_correctly(temp_db):
    temp_db.save_quote("line:U1", {"layer": 6, "qty": 1}, {"status": "success", "total": 100.0, "unit_price": 100.0})
    temp_db.save_quote("line:U1", {"layer": 6, "qty": 1}, {"status": "success", "total": 200.0, "unit_price": 200.0})
    temp_db.save_quote("line:U1", {"layer": 8, "qty": 1}, {"status": "success", "total": 50.0, "unit_price": 50.0})

    stats = {row["layer"]: row for row in temp_db.get_stats_by_layer()}
    assert stats[6]["count"] == 2
    assert stats[6]["total"] == 300.0
    assert stats[8]["count"] == 1


def test_get_stats_by_material_groups_correctly(temp_db):
    temp_db.save_quote("line:U1", {"layer": 6, "material": "FR4", "qty": 1}, {"status": "success", "total": 100.0, "unit_price": 100.0})
    temp_db.save_quote("line:U1", {"layer": 6, "material": "FR4", "qty": 1}, {"status": "success", "total": 100.0, "unit_price": 100.0})

    stats = {row["material"]: row for row in temp_db.get_stats_by_material()}
    assert stats["FR4"]["count"] == 2
