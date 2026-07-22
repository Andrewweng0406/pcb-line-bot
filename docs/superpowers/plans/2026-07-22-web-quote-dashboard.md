# Web Quote Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an internal, login-protected web app to `pcb_line_bot` that lets staff create, browse, edit, and track PCB quotes, reusing the existing `quote_engine`/`ai_parser`/`image_parser`, while the LINE bot keeps working unchanged as a secondary channel.

**Architecture:** One FastAPI app, extended in place. New `app/web.py` router (Jinja2 + HTMX + Alpine.js server-rendered pages, session-cookie auth) mounted alongside the existing `app/api.py` JSON router in `app/main.py`. No new repo, no frontend build step, no LINE bot code changes beyond what `save_quote` needs to stay backward compatible.

**Tech Stack:** FastAPI, Jinja2 (`fastapi.templating.Jinja2Templates`), HTMX + Alpine.js (loaded from CDN in `templates/base.html`, no npm/build step), Tailwind CSS (CDN, no build step), SQLAlchemy (existing), `passlib[bcrypt]` for password hashing, `itsdangerous` for signed session cookies, `pytest` + FastAPI `TestClient` for tests.

## Global Constraints

- All code, comments, docstrings, and docs are English. All text a human user sees in the browser (labels, buttons, messages) is Traditional Chinese — this codebase serves Chinese-speaking staff. See `docs/superpowers/specs/2026-07-22-web-quote-dashboard-design.md` for the full rationale.
- No role-based permissions — every logged-in `User` has equal access.
- No new repo/build pipeline — templates are server-rendered, CSS/JS via CDN `<script>`/`<link>` tags in `templates/base.html`.
- The LINE bot flow in `app/main.py` must keep working unmodified except for the `save_quote(...)` call sites picking up new optional keyword arguments with safe defaults.
- No Alembic — this project has no migration framework yet. Schema changes are applied via a small hand-rolled, idempotent migration function in `app/core/database.py` (see Task 3). This is a deliberate scope cut: introducing Alembic is a bigger, separate infra task not needed for a single evolving table at this stage.
- Do not modify `README.md` or `WEB_DASHBOARD_SPEC.md` in this plan — a separate, concurrent workstream (tracked outside this plan) is translating those files to English on another branch, and touching them here would create merge conflicts.

---

### Task 1: Add new dependencies and session secret setting

**Files:**
- Modify: `requirements.txt`
- Modify: `app/core/config.py`

**Interfaces:**
- Produces: `settings.SECRET_KEY: str` (used by Task 2's `app/core/auth.py`).

- [ ] **Step 1: Add new dependencies**

Append to `requirements.txt`:

```
jinja2==3.1.4
itsdangerous==2.2.0
passlib[bcrypt]==1.7.4
bcrypt==4.2.1
pytest==8.3.4
httpx==0.28.1
```

- [ ] **Step 2: Add `SECRET_KEY` setting**

In `app/core/config.py`, inside `class Settings(BaseSettings):`, after the `DEBUG` line, add:

```python
    # Web session signing key — set a real random value via env var in production
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-change-me")
```

- [ ] **Step 3: Install dependencies**

Run: `pip install -r requirements.txt`
Expected: all packages install without error.

- [ ] **Step 4: Commit**

```bash
git add requirements.txt app/core/config.py
git commit -m "Add web dashboard dependencies and session secret setting"
```

---

### Task 2: Password hashing and session token helpers

**Files:**
- Create: `app/core/auth.py`
- Test: `tests/test_auth.py`
- Create: `tests/__init__.py` (empty file, makes `tests` a package)

**Interfaces:**
- Consumes: `settings.SECRET_KEY` (Task 1).
- Produces: `hash_password(password: str) -> str`, `verify_password(password: str, password_hash: str) -> bool`, `create_session_token(user_id: int) -> str`, `read_session_token(token: str) -> int | None`. These four are used by Task 3 (`scripts/create_user.py`) and Task 5 (`app/web.py`).

- [ ] **Step 1: Write the failing test**

Create `tests/__init__.py` (empty).

Create `tests/test_auth.py`:

```python
from app.core.auth import (
    hash_password,
    verify_password,
    create_session_token,
    read_session_token,
)


def test_hash_password_does_not_return_plaintext():
    hashed = hash_password("s3cr3t-password")
    assert hashed != "s3cr3t-password"


def test_verify_password_accepts_correct_password():
    hashed = hash_password("s3cr3t-password")
    assert verify_password("s3cr3t-password", hashed) is True


def test_verify_password_rejects_wrong_password():
    hashed = hash_password("s3cr3t-password")
    assert verify_password("wrong-password", hashed) is False


def test_session_token_roundtrip():
    token = create_session_token(user_id=42)
    assert read_session_token(token) == 42


def test_read_session_token_rejects_garbage():
    assert read_session_token("not-a-real-token") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_auth.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.core.auth'`

- [ ] **Step 3: Write the implementation**

Create `app/core/auth.py`:

```python
from typing import Optional

from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 7  # 7 days
SESSION_SALT = "web-session"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.SECRET_KEY, salt=SESSION_SALT)


def create_session_token(user_id: int) -> str:
    return _serializer().dumps({"user_id": user_id})


def read_session_token(token: str) -> Optional[int]:
    try:
        data = _serializer().loads(token, max_age=SESSION_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired, ValueError):
        return None
    return data.get("user_id")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_auth.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add app/core/auth.py tests/__init__.py tests/test_auth.py
git commit -m "Add password hashing and session token helpers"
```

---

### Task 3: Database models — User, Customer, QuoteHistory extension

**Files:**
- Modify: `app/core/database.py`
- Test: `tests/test_database.py`
- Test: `tests/conftest.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `User(id, email, password_hash, created_at)`, `Customer(id, company_name, contact, phone, email, common_specs, created_at)`. `QuoteHistory` gains: `source_channel_id` (renamed from `customer_id`), `customer_id` (FK → Customer, int, nullable), `status` (str, default `"pending"`), `notes` (text, nullable), `quote_no` (str, nullable), `spec_json` (JSON, nullable), `breakdown_json` (JSON, nullable), `created_by_user_id`/`updated_by_user_id` (FK → User, nullable), plus relationships `customer`, `created_by`, `updated_by`.
  `save_quote(source_channel_id: str, parsed: dict, result: dict, customer_id: int = None, created_by_user_id: int = None) -> bool` — new signature, backward compatible with existing positional calls in `app/main.py`.
  `get_stats_by_layer() -> list[dict]` and `get_stats_by_material() -> list[dict]` — new shared helpers (moved out of `app/api.py` in Task 13, but defined here so both `app/api.py` and `app/web.py` can import them without duplicating the aggregation loop).
  These are used by Task 4 (`scripts/create_user.py`), Task 5 onward (`app/web.py`), and Task 13 (`app/api.py`).

- [ ] **Step 1: Write the failing test**

Create `tests/conftest.py`:

```python
import os
import tempfile

import pytest


@pytest.fixture()
def temp_db(monkeypatch):
    """Point the app at a fresh, empty SQLite file for the duration of one test."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    # app.core.database creates its engine at import time from settings, so
    # modules that already imported it need a fresh reload against the new URL.
    import importlib
    import app.core.config as config_module
    config_module.get_settings.cache_clear()
    import app.core.database as database_module
    importlib.reload(database_module)
    database_module.init_db()

    yield database_module

    os.remove(db_path)
```

Create `tests/test_database.py`:

```python
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


def test_migration_renames_old_customer_id_column(temp_db):
    """Simulate a pre-migration row (old schema had a string `customer_id` column
    holding the LINE user id) and confirm the migration renamed it to
    `source_channel_id` without losing data, by inserting through the raw
    column that exists post-migration.
    """
    from sqlalchemy import inspect

    inspector = inspect(temp_db.engine)
    columns = {col["name"] for col in inspector.get_columns("quote_history")}
    assert "source_channel_id" in columns
    assert "customer_id" in columns  # new FK column, re-added after rename
    assert "spec_json" in columns
    assert "breakdown_json" in columns
    assert "created_by_user_id" in columns
    assert "updated_by_user_id" in columns


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_database.py -v`
Expected: FAIL — `AttributeError: module 'app.core.database' has no attribute 'User'` (and similar for `Customer`, `get_stats_by_layer`, etc.)

- [ ] **Step 3: Write the implementation**

In `app/core/database.py`, replace the imports at the top with:

```python
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, DateTime, Text, JSON,
    ForeignKey, func, inspect, text
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from datetime import datetime
from app.core.config import settings
from app.core.logging import get_logger
```

Replace the `QuoteHistory` class with:

```python
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String(255), nullable=False, index=True)
    contact = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    common_specs = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class QuoteHistory(Base):
    __tablename__ = "quote_history"

    id = Column(Integer, primary_key=True, index=True)
    # Who/what submitted this quote: a LINE user_id (e.g. "Uabc123...") or a
    # web session token (e.g. "web:<user_id>"). Not a business customer.
    source_channel_id = Column(String(255), index=True)
    # The actual business customer this quote is for, if known/linked.
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True, index=True)
    layer = Column(Integer)
    material = Column(String(100))
    length_mm = Column(Float, nullable=True)
    width_mm = Column(Float, nullable=True)
    qty = Column(Integer)
    issue_ratio = Column(Float, default=1.0)
    total = Column(Float)
    unit_price = Column(Float)
    status = Column(String(20), default="pending", index=True)
    notes = Column(Text, nullable=True)
    quote_no = Column(String(50), nullable=True, index=True)
    # Full parsed input / full calculate_quote() output, kept as JSON so new
    # fields added to the parser or quote engine don't require a migration.
    spec_json = Column(JSON, nullable=True)
    breakdown_json = Column(JSON, nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    customer = relationship("Customer")
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    updated_by = relationship("User", foreign_keys=[updated_by_user_id])
```

Add the migration function and call it from `init_db()`:

```python
def _run_migrations(engine) -> None:
    """Hand-rolled, idempotent additive migration. No Alembic yet — see
    Global Constraints in the implementation plan for why.
    """
    inspector = inspect(engine)
    if "quote_history" not in inspector.get_table_names():
        return  # fresh database, create_all() already built the current schema

    columns = {col["name"] for col in inspector.get_columns("quote_history")}

    with engine.begin() as conn:
        if "source_channel_id" not in columns and "customer_id" in columns:
            conn.execute(text(
                "ALTER TABLE quote_history RENAME COLUMN customer_id TO source_channel_id"
            ))
            columns.discard("customer_id")
            columns.add("source_channel_id")

        additions = {
            "customer_id": "INTEGER",
            "status": "VARCHAR(20) DEFAULT 'pending'",
            "notes": "TEXT",
            "quote_no": "VARCHAR(50)",
            "spec_json": "JSON",
            "breakdown_json": "JSON",
            "created_by_user_id": "INTEGER",
            "updated_by_user_id": "INTEGER",
        }
        for column_name, column_type in additions.items():
            if column_name not in columns:
                conn.execute(text(
                    f"ALTER TABLE quote_history ADD COLUMN {column_name} {column_type}"
                ))


def init_db():
    Base.metadata.create_all(bind=engine)
    _run_migrations(engine)
    logger.info("Database initialized")
```

Replace `save_quote` with:

```python
def _generate_quote_no(db: Session) -> str:
    today_str = datetime.utcnow().strftime("%Y%m%d")
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    count_today = db.query(func.count(QuoteHistory.id)).filter(
        QuoteHistory.created_at >= today_start
    ).scalar() or 0
    return f"PCB-{today_str}-{count_today + 1:03d}"


def save_quote(
    source_channel_id: str,
    parsed: dict,
    result: dict,
    customer_id: int = None,
    created_by_user_id: int = None,
) -> bool:
    try:
        db = SessionLocal()
        quote = QuoteHistory(
            source_channel_id=source_channel_id,
            customer_id=customer_id,
            layer=parsed.get("layer"),
            material=parsed.get("material"),
            length_mm=parsed.get("length_mm"),
            width_mm=parsed.get("width_mm"),
            qty=parsed.get("qty"),
            issue_ratio=result.get("issue_ratio", 1.0),
            total=result.get("total"),
            unit_price=result.get("unit_price"),
            status="pending",
            quote_no=_generate_quote_no(db),
            spec_json=parsed,
            breakdown_json=result,
            created_by_user_id=created_by_user_id,
        )
        db.add(quote)
        db.commit()
        db.close()
        logger.info(f"Quote saved for channel {source_channel_id}")
        return True
    except Exception as e:
        logger.error(f"Error saving quote: {e}")
        return False
```

Add shared stats helpers (near `get_system_stats`):

```python
def get_stats_by_layer() -> list:
    db = SessionLocal()
    quotes = db.query(QuoteHistory).all()
    db.close()

    stats = {}
    for q in quotes:
        layer = q.layer
        if layer not in stats:
            stats[layer] = {"count": 0, "total": 0}
        stats[layer]["count"] += 1
        stats[layer]["total"] += q.total or 0

    return [
        {"layer": k, "count": v["count"], "total": round(v["total"], 2)}
        for k, v in sorted(stats.items())
    ]


def get_stats_by_material() -> list:
    db = SessionLocal()
    quotes = db.query(QuoteHistory).all()
    db.close()

    stats = {}
    for q in quotes:
        material = q.material or "Unknown"
        if material not in stats:
            stats[material] = {"count": 0, "total": 0}
        stats[material]["count"] += 1
        stats[material]["total"] += q.total or 0

    return [
        {"material": k, "count": v["count"], "total": round(v["total"], 2)}
        for k, v in sorted(stats.items())
    ]
```

Update `get_recent_quotes` and `search_quotes`' return tuples — they currently
select from a `QuoteHistory` whose columns are unchanged for `layer`,
`material`, `total`, `created_at`, so no change needed there.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_database.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add app/core/database.py tests/conftest.py tests/test_database.py
git commit -m "Add User/Customer models and extend QuoteHistory for the web dashboard"
```

---

### Task 4: CLI script to create a web login account

**Files:**
- Create: `scripts/create_user.py`
- Test: `tests/test_create_user_script.py`

**Interfaces:**
- Consumes: `app.core.database.{init_db, SessionLocal, User}`, `app.core.auth.hash_password`.
- Produces: `create_user(email: str, password: str) -> None` (importable, used by the test and by the `__main__` CLI entry point).

- [ ] **Step 1: Write the failing test**

Create `tests/test_create_user_script.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_create_user_script.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'create_user'`

- [ ] **Step 3: Write the implementation**

Create `scripts/create_user.py`:

```python
"""CLI to create a web login account.

Usage: python scripts/create_user.py <email> <password>
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.database import init_db, SessionLocal, User  # noqa: E402
from app.core.auth import hash_password  # noqa: E402


def create_user(email: str, password: str) -> None:
    init_db()
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            print(f"User already exists: {email}")
            return
        user = User(email=email, password_hash=hash_password(password))
        db.add(user)
        db.commit()
        print(f"Created user: {email}")
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python scripts/create_user.py <email> <password>")
        sys.exit(1)
    create_user(sys.argv[1], sys.argv[2])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_create_user_script.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/create_user.py tests/test_create_user_script.py
git commit -m "Add CLI script to create web login accounts"
```

---

### Task 5: Web router skeleton, login/logout, base template

**Files:**
- Create: `app/web.py`
- Create: `templates/base.html`
- Create: `templates/login.html`
- Test: `tests/test_web_auth.py`

**Interfaces:**
- Consumes: `app.core.auth.{verify_password, create_session_token, read_session_token}`, `app.core.database.{SessionLocal, User}`.
- Produces: `router` (FastAPI `APIRouter`, mounted in Task 15), `get_current_user_optional(session: Optional[str]) -> Optional[User]` dependency (used by every page task from here on), `SESSION_COOKIE_NAME = "session"`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_web_auth.py`:

```python
from fastapi.testclient import TestClient

from app.core.auth import hash_password


def _make_client(temp_db):
    from app.main import app
    return TestClient(app)


def _create_user(temp_db, email="staff@example.com", password="hunter2"):
    db = temp_db.SessionLocal()
    user = temp_db.User(email=email, password_hash=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    return user


def test_dashboard_redirects_when_logged_out(temp_db):
    client = _make_client(temp_db)
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_login_with_correct_credentials_sets_session_and_redirects(temp_db):
    _create_user(temp_db)
    client = _make_client(temp_db)

    response = client.post(
        "/login",
        data={"email": "staff@example.com", "password": "hunter2"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert "session" in response.cookies


def test_login_with_wrong_password_shows_error(temp_db):
    _create_user(temp_db)
    client = _make_client(temp_db)

    response = client.post(
        "/login",
        data={"email": "staff@example.com", "password": "wrong"},
        follow_redirects=False,
    )
    assert response.status_code == 401
    assert "session" not in response.cookies


def test_dashboard_loads_when_logged_in(temp_db):
    _create_user(temp_db)
    client = _make_client(temp_db)
    client.post("/login", data={"email": "staff@example.com", "password": "hunter2"})

    response = client.get("/")
    assert response.status_code == 200


def test_logout_clears_session(temp_db):
    _create_user(temp_db)
    client = _make_client(temp_db)
    client.post("/login", data={"email": "staff@example.com", "password": "hunter2"})

    client.get("/logout")
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_web_auth.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.web'` (once Task 15 mounts it) or 404 on `/login` until the router exists and is mounted. Mount the router now (temporarily, fully, since Task 15 just adds the remaining includes) by adding the two lines below to `app/main.py` as part of this task, so the test can pass:

In `app/main.py`, after `app.include_router(api_router)`, add:

```python
from app.web import router as web_router  # noqa: E402

app.include_router(web_router)
```

- [ ] **Step 3: Write the implementation**

Create `templates/base.html`:

```html
<!DOCTYPE html>
<html lang="zh-Hant">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}PCB 報價系統{% endblock %}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/htmx.org@1.9.12"></script>
    <script src="https://unpkg.com/alpinejs@3.14.1/dist/cdn.min.js" defer></script>
</head>
<body class="bg-slate-50 text-slate-900 min-h-screen">
    {% if user %}
    <nav class="bg-white border-b border-slate-200 px-6 py-3 flex items-center gap-6">
        <a href="/" class="font-semibold text-blue-600">PCB 報價系統</a>
        <a href="/quotes/new" class="text-sm text-slate-600 hover:text-blue-600">新增報價</a>
        <a href="/quotes" class="text-sm text-slate-600 hover:text-blue-600">報價列表</a>
        <a href="/customers" class="text-sm text-slate-600 hover:text-blue-600">客戶管理</a>
        <a href="/stats" class="text-sm text-slate-600 hover:text-blue-600">統計報告</a>
        <span class="ml-auto text-sm text-slate-500">{{ user.email }}</span>
        <a href="/logout" class="text-sm text-red-500 hover:text-red-700">登出</a>
    </nav>
    {% endif %}
    <main class="max-w-6xl mx-auto p-6">
        {% block content %}{% endblock %}
    </main>
</body>
</html>
```

Create `templates/login.html`:

```html
{% extends "base.html" %}
{% block title %}登入 - PCB 報價系統{% endblock %}
{% block content %}
<div class="max-w-sm mx-auto mt-24 bg-white rounded-xl shadow p-8">
    <h1 class="text-xl font-semibold mb-6 text-center">PCB 報價系統登入</h1>
    {% if error %}
    <p class="text-red-600 text-sm mb-4">{{ error }}</p>
    {% endif %}
    <form method="post" action="/login" class="space-y-4">
        <div>
            <label class="block text-sm text-slate-600 mb-1">帳號 (Email)</label>
            <input type="email" name="email" required class="w-full border border-slate-300 rounded-lg px-3 py-2">
        </div>
        <div>
            <label class="block text-sm text-slate-600 mb-1">密碼</label>
            <input type="password" name="password" required class="w-full border border-slate-300 rounded-lg px-3 py-2">
        </div>
        <button type="submit" class="w-full bg-blue-600 text-white rounded-lg py-2 font-medium hover:bg-blue-700">
            登入
        </button>
    </form>
</div>
{% endblock %}
```

Create `app/web.py`:

```python
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.auth import (
    create_session_token,
    read_session_token,
    verify_password,
)
from app.core.database import SessionLocal, User
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["web"])
templates = Jinja2Templates(directory="templates")

SESSION_COOKIE_NAME = "session"


def get_current_user_optional(
    session: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE_NAME)
) -> Optional[User]:
    if not session:
        return None
    user_id = read_session_token(session)
    if user_id is None:
        return None
    db = SessionLocal()
    user = db.query(User).filter(User.id == user_id).first()
    db.close()
    return user


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login")
def login_submit(request: Request, email: str = Form(...), password: str = Form(...)):
    db = SessionLocal()
    user = db.query(User).filter(User.email == email).first()
    db.close()

    if user is None or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "帳號或密碼錯誤"},
            status_code=401,
        )

    token = create_session_token(user.id)
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        SESSION_COOKIE_NAME, token, httponly=True, max_age=60 * 60 * 24 * 7
    )
    return response


@router.get("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE_NAME)
    return response


@router.get("/", response_class=HTMLResponse)
def dashboard(
    request: Request, user: Optional[User] = Depends(get_current_user_optional)
):
    if user is None:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        "base.html", {"request": request, "user": user}
    )
```

(The dashboard route body is filled in for real in Task 6 — this task only needs it to prove login/redirect behavior.)

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_web_auth.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add app/web.py app/main.py templates/base.html templates/login.html tests/test_web_auth.py
git commit -m "Add web login/logout and session-cookie auth dependency"
```

---

### Task 6: Dashboard home page

**Files:**
- Modify: `app/web.py` (the `dashboard` route body)
- Create: `templates/dashboard.html`
- Test: `tests/test_web_dashboard.py`

**Interfaces:**
- Consumes: `app.core.database.get_system_stats() -> dict` (existing function).

- [ ] **Step 1: Write the failing test**

Create `tests/test_web_dashboard.py`:

```python
from fastapi.testclient import TestClient

from app.core.auth import hash_password


def _logged_in_client(temp_db):
    from app.main import app
    client = TestClient(app)
    db = temp_db.SessionLocal()
    user = temp_db.User(email="staff@example.com", password_hash=hash_password("hunter2"))
    db.add(user)
    db.commit()
    db.close()
    client.post("/login", data={"email": "staff@example.com", "password": "hunter2"})
    return client


def test_dashboard_shows_stats(temp_db):
    temp_db.save_quote("line:U1", {"layer": 6, "qty": 1}, {"status": "success", "total": 100.0, "unit_price": 100.0})
    client = _logged_in_client(temp_db)

    response = client.get("/")
    assert response.status_code == 200
    assert "報價" in response.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_web_dashboard.py -v`
Expected: FAIL — `jinja2.exceptions.TemplateNotFound: dashboard.html` (route still renders `base.html` directly from Task 5, no stats context, template missing)

- [ ] **Step 3: Write the implementation**

In `app/web.py`, add the import `from app.core.database import get_system_stats` and replace the `dashboard` route body:

```python
@router.get("/", response_class=HTMLResponse)
def dashboard(
    request: Request, user: Optional[User] = Depends(get_current_user_optional)
):
    if user is None:
        return RedirectResponse(url="/login", status_code=303)
    stats = get_system_stats()
    return templates.TemplateResponse(
        "dashboard.html", {"request": request, "user": user, "stats": stats}
    )
```

Create `templates/dashboard.html`:

```html
{% extends "base.html" %}
{% block title %}儀表板 - PCB 報價系統{% endblock %}
{% block content %}
<h1 class="text-2xl font-semibold mb-6">儀表板</h1>
<div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
    <div class="bg-white rounded-xl shadow p-6">
        <p class="text-sm text-slate-500">今日報價數</p>
        <p class="text-3xl font-bold text-blue-600">{{ stats.today_count }}</p>
    </div>
    <div class="bg-white rounded-xl shadow p-6">
        <p class="text-sm text-slate-500">歷史總報價數</p>
        <p class="text-3xl font-bold text-blue-600">{{ stats.total_count }}</p>
    </div>
    <div class="bg-white rounded-xl shadow p-6">
        <p class="text-sm text-slate-500">平均報價金額</p>
        <p class="text-3xl font-bold text-blue-600">NT$ {{ "{:,.0f}".format(stats.avg_price) }}</p>
    </div>
</div>
<div class="mt-8 flex gap-3">
    <a href="/quotes/new" class="bg-blue-600 text-white rounded-lg px-4 py-2 text-sm font-medium hover:bg-blue-700">
        + 新增報價
    </a>
    <a href="/quotes" class="bg-white border border-slate-300 rounded-lg px-4 py-2 text-sm font-medium hover:bg-slate-100">
        查看報價列表
    </a>
</div>
{% endblock %}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_web_dashboard.py -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add app/web.py templates/dashboard.html tests/test_web_dashboard.py
git commit -m "Add dashboard home page with stat cards"
```

---

### Task 7: New quote page — structured form + submit

**Files:**
- Modify: `app/web.py`
- Create: `templates/quote_new.html`
- Create: `templates/_quote_form_fields.html`
- Test: `tests/test_web_quote_new.py`

**Interfaces:**
- Consumes: `app.quote_engine.calculate_quote(data: dict) -> dict`, `app.core.database.{save_quote, Customer, SessionLocal}`.
- Produces: `GET/POST /quotes/new` route. `templates/_quote_form_fields.html` is a partial reused by Task 8's AI-assist endpoint.

- [ ] **Step 1: Write the failing test**

Create `tests/test_web_quote_new.py`:

```python
from fastapi.testclient import TestClient

from app.core.auth import hash_password


def _logged_in_client(temp_db):
    from app.main import app
    client = TestClient(app)
    db = temp_db.SessionLocal()
    user = temp_db.User(email="staff@example.com", password_hash=hash_password("hunter2"))
    db.add(user)
    db.commit()
    db.close()
    client.post("/login", data={"email": "staff@example.com", "password": "hunter2"})
    return client


def test_new_quote_form_loads(temp_db):
    client = _logged_in_client(temp_db)
    response = client.get("/quotes/new")
    assert response.status_code == 200
    assert "新增報價" in response.text


def test_submitting_quote_creates_row_and_links_customer(temp_db):
    client = _logged_in_client(temp_db)

    response = client.post(
        "/quotes/new",
        data={
            "layer": 6,
            "qty": 9,
            "material": "FR4",
            "length_mm": 100,
            "width_mm": 100,
            "issue_ratio": 1.0,
            "company_name": "ABC Corp",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/quotes"

    db = temp_db.SessionLocal()
    quote = db.query(temp_db.QuoteHistory).order_by(temp_db.QuoteHistory.id.desc()).first()
    assert quote.layer == 6
    assert quote.customer.company_name == "ABC Corp"
    assert quote.created_by.email == "staff@example.com"
    assert quote.spec_json["material"] == "FR4"
    db.close()


def test_submitting_invalid_quote_shows_error(temp_db):
    client = _logged_in_client(temp_db)

    response = client.post(
        "/quotes/new",
        data={"layer": 999, "qty": 1},
    )
    assert response.status_code == 400
    assert "暫不支持" in response.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_web_quote_new.py -v`
Expected: FAIL — 404 on `/quotes/new` (route doesn't exist yet)

- [ ] **Step 3: Write the implementation**

In `app/web.py`, add imports:

```python
from app.core.database import Customer, save_quote
from app.quote_engine import calculate_quote
```

Add routes:

```python
@router.get("/quotes/new", response_class=HTMLResponse)
def new_quote_page(
    request: Request, user: Optional[User] = Depends(get_current_user_optional)
):
    if user is None:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        "quote_new.html", {"request": request, "user": user, "error": None, "form": {}}
    )


@router.post("/quotes/new")
def create_quote(
    request: Request,
    layer: int = Form(...),
    qty: int = Form(...),
    material: str = Form(""),
    length_mm: Optional[float] = Form(None),
    width_mm: Optional[float] = Form(None),
    issue_ratio: float = Form(1.0),
    enig: Optional[str] = Form(None),
    enig_thickness_uinch: Optional[float] = Form(None),
    vip: Optional[str] = Form(None),
    impedance: Optional[str] = Form(None),
    back_drill: Optional[str] = Form(None),
    bvh: Optional[str] = Form(None),
    thickness_mm: Optional[float] = Form(None),
    pitch_mm: Optional[float] = Form(None),
    delivery_days: Optional[int] = Form(None),
    company_name: str = Form(""),
    user: Optional[User] = Depends(get_current_user_optional),
):
    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    parsed = {
        "layer": layer,
        "qty": qty,
        "material": material or None,
        "length_mm": length_mm,
        "width_mm": width_mm,
        "issue_ratio": issue_ratio,
        "enig": enig is not None,
        "enig_thickness_uinch": enig_thickness_uinch,
        "vip": vip is not None,
        "impedance": impedance is not None,
        "back_drill": back_drill is not None,
        "bvh": bvh is not None,
        "thickness_mm": thickness_mm,
        "pitch_mm": pitch_mm,
        "delivery_days": delivery_days,
        "company_name": company_name or None,
    }

    result = calculate_quote(parsed)

    if result.get("status") != "success":
        return templates.TemplateResponse(
            "quote_new.html",
            {
                "request": request,
                "user": user,
                "error": result.get("message"),
                "form": parsed,
            },
            status_code=400,
        )

    customer_id = None
    if company_name:
        db = SessionLocal()
        customer = db.query(Customer).filter(Customer.company_name == company_name).first()
        if customer is None:
            customer = Customer(company_name=company_name)
            db.add(customer)
            db.commit()
            db.refresh(customer)
        customer_id = customer.id
        db.close()

    save_quote(
        source_channel_id=f"web:{user.id}",
        parsed=parsed,
        result=result,
        customer_id=customer_id,
        created_by_user_id=user.id,
    )

    return RedirectResponse(url="/quotes", status_code=303)
```

Create `templates/_quote_form_fields.html` (the reusable fields block, standalone so both the full page and the HTMX partial response in Task 8 can render it):

```html
{% if ai_error %}
<p class="text-amber-600 text-sm mb-3">{{ ai_error }}</p>
{% endif %}
<div class="grid grid-cols-2 gap-4">
    <div>
        <label class="block text-sm text-slate-600 mb-1">層數 (Layer)</label>
        <input type="number" name="layer" required value="{{ form.layer or '' }}" class="w-full border border-slate-300 rounded-lg px-3 py-2">
    </div>
    <div>
        <label class="block text-sm text-slate-600 mb-1">數量 (Qty)</label>
        <input type="number" name="qty" required value="{{ form.qty or '' }}" class="w-full border border-slate-300 rounded-lg px-3 py-2">
    </div>
    <div>
        <label class="block text-sm text-slate-600 mb-1">材料 (Material)</label>
        <input type="text" name="material" value="{{ form.material or '' }}" class="w-full border border-slate-300 rounded-lg px-3 py-2">
    </div>
    <div>
        <label class="block text-sm text-slate-600 mb-1">客戶公司名稱</label>
        <input type="text" name="company_name" value="{{ form.company_name or '' }}" class="w-full border border-slate-300 rounded-lg px-3 py-2">
    </div>
    <div>
        <label class="block text-sm text-slate-600 mb-1">長 (mm)</label>
        <input type="number" step="0.01" name="length_mm" value="{{ form.length_mm or '' }}" class="w-full border border-slate-300 rounded-lg px-3 py-2">
    </div>
    <div>
        <label class="block text-sm text-slate-600 mb-1">寬 (mm)</label>
        <input type="number" step="0.01" name="width_mm" value="{{ form.width_mm or '' }}" class="w-full border border-slate-300 rounded-lg px-3 py-2">
    </div>
    <div>
        <label class="block text-sm text-slate-600 mb-1">投料率</label>
        <input type="number" step="0.01" name="issue_ratio" value="{{ form.issue_ratio or 1.0 }}" class="w-full border border-slate-300 rounded-lg px-3 py-2">
    </div>
    <div>
        <label class="block text-sm text-slate-600 mb-1">交期 (天)</label>
        <input type="number" name="delivery_days" value="{{ form.delivery_days or '' }}" class="w-full border border-slate-300 rounded-lg px-3 py-2">
    </div>
    <div>
        <label class="block text-sm text-slate-600 mb-1">Pitch (mm)</label>
        <input type="number" step="0.01" name="pitch_mm" value="{{ form.pitch_mm or '' }}" class="w-full border border-slate-300 rounded-lg px-3 py-2">
    </div>
    <div>
        <label class="block text-sm text-slate-600 mb-1">板厚 (mm)</label>
        <input type="number" step="0.01" name="thickness_mm" value="{{ form.thickness_mm or '' }}" class="w-full border border-slate-300 rounded-lg px-3 py-2">
    </div>
    <div>
        <label class="block text-sm text-slate-600 mb-1">ENIG 厚度 (u")</label>
        <input type="number" step="0.01" name="enig_thickness_uinch" value="{{ form.enig_thickness_uinch or '' }}" class="w-full border border-slate-300 rounded-lg px-3 py-2">
    </div>
</div>
<div class="grid grid-cols-4 gap-4 mt-4">
    <label class="flex items-center gap-2 text-sm">
        <input type="checkbox" name="enig" {% if form.enig %}checked{% endif %}> ENIG
    </label>
    <label class="flex items-center gap-2 text-sm">
        <input type="checkbox" name="vip" {% if form.vip %}checked{% endif %}> VIP
    </label>
    <label class="flex items-center gap-2 text-sm">
        <input type="checkbox" name="impedance" {% if form.impedance %}checked{% endif %}> Impedance
    </label>
    <label class="flex items-center gap-2 text-sm">
        <input type="checkbox" name="back_drill" {% if form.back_drill %}checked{% endif %}> Back Drill
    </label>
    <label class="flex items-center gap-2 text-sm">
        <input type="checkbox" name="bvh" {% if form.bvh %}checked{% endif %}> BVH
    </label>
</div>
```

Create `templates/quote_new.html`:

```html
{% extends "base.html" %}
{% block title %}新增報價 - PCB 報價系統{% endblock %}
{% block content %}
<h1 class="text-2xl font-semibold mb-6">新增報價</h1>

{% if error %}
<p class="text-red-600 text-sm mb-4">{{ error }}</p>
{% endif %}

<div class="bg-white rounded-xl shadow p-6 mb-6">
    <h2 class="font-medium mb-3">AI 輔助填單</h2>
    <div class="flex gap-3 items-end">
        <div class="flex-1">
            <label class="block text-sm text-slate-600 mb-1">貼上規格文字</label>
            <textarea
                id="ai-spec-text"
                name="spec_text"
                rows="2"
                class="w-full border border-slate-300 rounded-lg px-3 py-2"
                placeholder="例如：6層 FR4 100x100mm 數量9 ENIG 10u"
            ></textarea>
        </div>
        <button
            type="button"
            hx-post="/quotes/new/ai-assist"
            hx-include="#ai-spec-text"
            hx-target="#quote-form-fields"
            hx-swap="innerHTML"
            class="bg-slate-800 text-white rounded-lg px-4 py-2 text-sm font-medium hover:bg-slate-900"
        >
            AI 解析並帶入表單
        </button>
    </div>
</div>

<form method="post" action="/quotes/new" class="bg-white rounded-xl shadow p-6">
    <div id="quote-form-fields">
        {% include "_quote_form_fields.html" %}
    </div>
    <button type="submit" class="mt-6 bg-blue-600 text-white rounded-lg px-6 py-2 font-medium hover:bg-blue-700">
        計算並儲存報價
    </button>
</form>
{% endblock %}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_web_quote_new.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add app/web.py templates/quote_new.html templates/_quote_form_fields.html tests/test_web_quote_new.py
git commit -m "Add structured new-quote form and submission handling"
```

---

### Task 8: AI-assist HTMX endpoint (paste text or upload a photo)

**Files:**
- Modify: `app/web.py`
- Test: `tests/test_web_ai_assist.py`

**Interfaces:**
- Consumes: `app.ai_parser.parse_pcb_text(text: str) -> dict`, `app.image_parser.parse_pcb_image(path: str) -> dict`, `app.core.storage.file_storage.cleanup(path: str)`.
- Produces: `POST /quotes/new/ai-assist`, returning the `_quote_form_fields.html` partial.

- [ ] **Step 1: Write the failing test**

Create `tests/test_web_ai_assist.py`:

```python
from fastapi.testclient import TestClient

from app.core.auth import hash_password


def _logged_in_client(temp_db):
    from app.main import app
    client = TestClient(app)
    db = temp_db.SessionLocal()
    user = temp_db.User(email="staff@example.com", password_hash=hash_password("hunter2"))
    db.add(user)
    db.commit()
    db.close()
    client.post("/login", data={"email": "staff@example.com", "password": "hunter2"})
    return client


def test_ai_assist_fills_form_from_text(temp_db, monkeypatch):
    import app.web as web_module

    monkeypatch.setattr(
        web_module,
        "parse_pcb_text",
        lambda text: {"layer": 6, "material": "FR4", "qty": 9},
    )

    client = _logged_in_client(temp_db)
    response = client.post("/quotes/new/ai-assist", data={"spec_text": "6層 FR4 數量9"})

    assert response.status_code == 200
    assert 'value="6"' in response.text
    assert 'value="FR4"' in response.text


def test_ai_assist_handles_parser_failure_gracefully(temp_db, monkeypatch):
    import app.web as web_module

    def _boom(text):
        raise RuntimeError("OpenAI timeout")

    monkeypatch.setattr(web_module, "parse_pcb_text", _boom)

    client = _logged_in_client(temp_db)
    response = client.post("/quotes/new/ai-assist", data={"spec_text": "6層 FR4"})

    assert response.status_code == 200
    assert "AI 解析失敗" in response.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_web_ai_assist.py -v`
Expected: FAIL — 404 on `/quotes/new/ai-assist`

- [ ] **Step 3: Write the implementation**

In `app/web.py`, add imports:

```python
import uuid

from fastapi import File, UploadFile
from app.ai_parser import parse_pcb_text
from app.image_parser import parse_pcb_image
from app.core.storage import file_storage
```

Add the route:

```python
@router.post("/quotes/new/ai-assist", response_class=HTMLResponse)
async def ai_assist(
    request: Request,
    spec_text: str = Form(""),
    photo: Optional[UploadFile] = File(None),
    user: Optional[User] = Depends(get_current_user_optional),
):
    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    parsed = {}
    ai_error = None
    try:
        if photo is not None and photo.filename:
            image_path = f"data/uploads/web_{uuid.uuid4().hex}.jpg"
            with open(image_path, "wb") as f:
                f.write(await photo.read())
            try:
                parsed = parse_pcb_image(image_path)
            finally:
                file_storage.cleanup(image_path)
        elif spec_text.strip():
            parsed = parse_pcb_text(spec_text)

        # ai_parser/image_parser emit "thickness" (see app/ai_parser.py's JSON
        # schema) but quote_engine.calculate_quote() and this form both key
        # board thickness as "thickness_mm" — normalize so AI-filled values
        # actually land in the form field.
        if "thickness" in parsed and "thickness_mm" not in parsed:
            parsed["thickness_mm"] = parsed.pop("thickness")
    except Exception as e:
        logger.error(f"AI assist failed: {e}")
        ai_error = "AI 解析失敗，請手動填寫規格"
        parsed = {}

    return templates.TemplateResponse(
        "_quote_form_fields.html",
        {"request": request, "form": parsed, "ai_error": ai_error},
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_web_ai_assist.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add app/web.py tests/test_web_ai_assist.py
git commit -m "Add AI-assist endpoint for pasted spec text and PCB photos"
```

---

### Task 9: Quotes list page with filters

**Files:**
- Modify: `app/web.py`
- Create: `templates/quotes_list.html`
- Test: `tests/test_web_quotes_list.py`

**Interfaces:**
- Consumes: `app.core.database.{SessionLocal, QuoteHistory, Customer}`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_web_quotes_list.py`:

```python
from fastapi.testclient import TestClient

from app.core.auth import hash_password


def _logged_in_client(temp_db):
    from app.main import app
    client = TestClient(app)
    db = temp_db.SessionLocal()
    user = temp_db.User(email="staff@example.com", password_hash=hash_password("hunter2"))
    db.add(user)
    db.commit()
    db.close()
    client.post("/login", data={"email": "staff@example.com", "password": "hunter2"})
    return client


def test_quotes_list_shows_all_quotes(temp_db):
    temp_db.save_quote("line:U1", {"layer": 6, "material": "FR4", "qty": 1}, {"status": "success", "total": 100.0, "unit_price": 100.0})
    temp_db.save_quote("line:U1", {"layer": 8, "material": "Megtron6", "qty": 1}, {"status": "success", "total": 200.0, "unit_price": 200.0})

    client = _logged_in_client(temp_db)
    response = client.get("/quotes")

    assert response.status_code == 200
    assert "FR4" in response.text
    assert "Megtron6" in response.text


def test_quotes_list_filters_by_layer(temp_db):
    temp_db.save_quote("line:U1", {"layer": 6, "material": "FR4", "qty": 1}, {"status": "success", "total": 100.0, "unit_price": 100.0})
    temp_db.save_quote("line:U1", {"layer": 8, "material": "Megtron6", "qty": 1}, {"status": "success", "total": 200.0, "unit_price": 200.0})

    client = _logged_in_client(temp_db)
    response = client.get("/quotes?layer=6")

    assert "FR4" in response.text
    assert "Megtron6" not in response.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_web_quotes_list.py -v`
Expected: FAIL — 404 on `/quotes`

- [ ] **Step 3: Write the implementation**

In `app/web.py`, add import `from app.core.database import QuoteHistory` (extend the existing `database` import line) and add:

```python
@router.get("/quotes", response_class=HTMLResponse)
def quotes_list(
    request: Request,
    status: Optional[str] = None,
    layer: Optional[int] = None,
    material: Optional[str] = None,
    customer: Optional[str] = None,
    user: Optional[User] = Depends(get_current_user_optional),
):
    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    db = SessionLocal()
    query = db.query(QuoteHistory)
    if status:
        query = query.filter(QuoteHistory.status == status)
    if layer:
        query = query.filter(QuoteHistory.layer == layer)
    if material:
        query = query.filter(QuoteHistory.material.ilike(f"%{material}%"))
    if customer:
        query = query.join(Customer).filter(Customer.company_name.ilike(f"%{customer}%"))
    quotes = query.order_by(QuoteHistory.created_at.desc()).limit(200).all()
    db.close()

    return templates.TemplateResponse(
        "quotes_list.html",
        {
            "request": request,
            "user": user,
            "quotes": quotes,
            "filters": {
                "status": status or "",
                "layer": layer or "",
                "material": material or "",
                "customer": customer or "",
            },
        },
    )
```

Create `templates/quotes_list.html`:

```html
{% extends "base.html" %}
{% block title %}報價列表 - PCB 報價系統{% endblock %}
{% block content %}
<h1 class="text-2xl font-semibold mb-6">報價列表</h1>

<form method="get" action="/quotes" class="bg-white rounded-xl shadow p-4 mb-6 flex flex-wrap gap-3 items-end">
    <div>
        <label class="block text-xs text-slate-500 mb-1">層數</label>
        <input type="number" name="layer" value="{{ filters.layer }}" class="border border-slate-300 rounded-lg px-3 py-1.5 text-sm">
    </div>
    <div>
        <label class="block text-xs text-slate-500 mb-1">材料</label>
        <input type="text" name="material" value="{{ filters.material }}" class="border border-slate-300 rounded-lg px-3 py-1.5 text-sm">
    </div>
    <div>
        <label class="block text-xs text-slate-500 mb-1">客戶</label>
        <input type="text" name="customer" value="{{ filters.customer }}" class="border border-slate-300 rounded-lg px-3 py-1.5 text-sm">
    </div>
    <div>
        <label class="block text-xs text-slate-500 mb-1">狀態</label>
        <select name="status" class="border border-slate-300 rounded-lg px-3 py-1.5 text-sm">
            <option value="" {% if not filters.status %}selected{% endif %}>全部</option>
            <option value="pending" {% if filters.status == "pending" %}selected{% endif %}>待審核</option>
            <option value="approved" {% if filters.status == "approved" %}selected{% endif %}>已批准</option>
            <option value="ordered" {% if filters.status == "ordered" %}selected{% endif %}>已下單</option>
        </select>
    </div>
    <button type="submit" class="bg-slate-800 text-white rounded-lg px-4 py-1.5 text-sm font-medium hover:bg-slate-900">
        篩選
    </button>
</form>

<div class="bg-white rounded-xl shadow overflow-x-auto">
    <table class="w-full text-sm">
        <thead class="bg-slate-100 text-slate-600 text-left">
            <tr>
                <th class="px-4 py-2">編號</th>
                <th class="px-4 py-2">客戶</th>
                <th class="px-4 py-2">層數</th>
                <th class="px-4 py-2">材料</th>
                <th class="px-4 py-2">總價</th>
                <th class="px-4 py-2">狀態</th>
                <th class="px-4 py-2">建立者</th>
                <th class="px-4 py-2">建立時間</th>
            </tr>
        </thead>
        <tbody>
            {% for q in quotes %}
            <tr class="border-t border-slate-100 hover:bg-slate-50">
                <td class="px-4 py-2"><a href="/quotes/{{ q.id }}" class="text-blue-600">{{ q.quote_no or q.id }}</a></td>
                <td class="px-4 py-2">{{ q.customer.company_name if q.customer else "-" }}</td>
                <td class="px-4 py-2">{{ q.layer }}L</td>
                <td class="px-4 py-2">{{ q.material or "-" }}</td>
                <td class="px-4 py-2">{{ "{:,.0f}".format(q.total or 0) }}</td>
                <td class="px-4 py-2">{{ q.status or "pending" }}</td>
                <td class="px-4 py-2">{{ q.created_by.email if q.created_by else "-" }}</td>
                <td class="px-4 py-2">{{ q.created_at.strftime("%Y-%m-%d %H:%M") }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endblock %}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_web_quotes_list.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add app/web.py templates/quotes_list.html tests/test_web_quotes_list.py
git commit -m "Add quotes list page with layer/material/customer/status filters"
```

---

### Task 10: Quote detail/edit page + export routes

**Files:**
- Modify: `app/web.py`
- Create: `templates/quote_detail.html`
- Test: `tests/test_web_quote_detail.py`

**Interfaces:**
- Consumes: `app.export_excel.export_quote_excel(spec: dict, result: dict) -> str`, `app.formal_quote_export.export_formal_quote(spec: dict, result: dict) -> str` (both existing, return a filename/path already used by `app/main.py`'s LINE flow).

- [ ] **Step 1: Write the failing test**

Create `tests/test_web_quote_detail.py`:

```python
from fastapi.testclient import TestClient

from app.core.auth import hash_password


def _logged_in_client(temp_db):
    from app.main import app
    client = TestClient(app)
    db = temp_db.SessionLocal()
    user = temp_db.User(email="staff@example.com", password_hash=hash_password("hunter2"))
    db.add(user)
    db.commit()
    db.close()
    client.post("/login", data={"email": "staff@example.com", "password": "hunter2"})
    return client


def test_quote_detail_shows_spec_and_breakdown(temp_db):
    temp_db.save_quote(
        "line:U1",
        {"layer": 6, "material": "FR4", "qty": 9},
        {"status": "success", "total": 12345.0, "unit_price": 1371.67, "issue_ratio": 1.0, "explanations": ["工程費: 80000"]},
    )
    db = temp_db.SessionLocal()
    quote_id = db.query(temp_db.QuoteHistory).order_by(temp_db.QuoteHistory.id.desc()).first().id
    db.close()

    client = _logged_in_client(temp_db)
    response = client.get(f"/quotes/{quote_id}")

    assert response.status_code == 200
    assert "12345" in response.text or "12,345" in response.text
    assert "待審核" in response.text


def test_quote_detail_missing_returns_404(temp_db):
    client = _logged_in_client(temp_db)
    response = client.get("/quotes/999")
    assert response.status_code == 404


def test_update_quote_status_and_notes(temp_db):
    temp_db.save_quote("line:U1", {"layer": 6, "qty": 1}, {"status": "success", "total": 100.0, "unit_price": 100.0})
    db = temp_db.SessionLocal()
    quote_id = db.query(temp_db.QuoteHistory).order_by(temp_db.QuoteHistory.id.desc()).first().id
    db.close()

    client = _logged_in_client(temp_db)
    response = client.post(
        f"/quotes/{quote_id}/update",
        data={"status": "approved", "notes": "customer confirmed"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    db = temp_db.SessionLocal()
    quote = db.query(temp_db.QuoteHistory).filter(temp_db.QuoteHistory.id == quote_id).first()
    assert quote.status == "approved"
    assert quote.notes == "customer confirmed"
    assert quote.updated_by.email == "staff@example.com"
    db.close()


def test_quote_missing_spec_json_renders_without_error(temp_db):
    """Pre-migration, LINE-submitted quotes may predate spec_json/breakdown_json.
    Simulate that by inserting a row with those columns left null.
    """
    db = temp_db.SessionLocal()
    quote = temp_db.QuoteHistory(
        source_channel_id="line:U1", layer=6, material="FR4", qty=1, total=100.0, unit_price=100.0
    )
    db.add(quote)
    db.commit()
    db.refresh(quote)
    quote_id = quote.id
    db.close()

    client = _logged_in_client(temp_db)
    response = client.get(f"/quotes/{quote_id}")
    assert response.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_web_quote_detail.py -v`
Expected: FAIL — 404 on `/quotes/{id}` (route doesn't exist yet)

- [ ] **Step 3: Write the implementation**

In `app/web.py`, add imports:

```python
from fastapi import HTTPException
from app.export_excel import export_quote_excel
from app.formal_quote_export import export_formal_quote
```

Add routes:

```python
STATUS_LABELS = {"pending": "待審核", "approved": "已批准", "ordered": "已下單"}


@router.get("/quotes/{quote_id}", response_class=HTMLResponse)
def quote_detail(
    request: Request,
    quote_id: int,
    user: Optional[User] = Depends(get_current_user_optional),
):
    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    db = SessionLocal()
    quote = db.query(QuoteHistory).filter(QuoteHistory.id == quote_id).first()
    db.close()

    if quote is None:
        raise HTTPException(status_code=404, detail="Quote not found")

    return templates.TemplateResponse(
        "quote_detail.html",
        {"request": request, "user": user, "quote": quote, "status_labels": STATUS_LABELS},
    )


@router.post("/quotes/{quote_id}/update")
def update_quote(
    quote_id: int,
    status: str = Form(...),
    notes: str = Form(""),
    user: Optional[User] = Depends(get_current_user_optional),
):
    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    db = SessionLocal()
    quote = db.query(QuoteHistory).filter(QuoteHistory.id == quote_id).first()
    if quote is None:
        db.close()
        raise HTTPException(status_code=404, detail="Quote not found")

    quote.status = status
    quote.notes = notes
    quote.updated_by_user_id = user.id
    db.commit()
    db.close()

    return RedirectResponse(url=f"/quotes/{quote_id}", status_code=303)


@router.get("/quotes/{quote_id}/export/excel")
def quote_export_excel(
    quote_id: int, user: Optional[User] = Depends(get_current_user_optional)
):
    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    db = SessionLocal()
    quote = db.query(QuoteHistory).filter(QuoteHistory.id == quote_id).first()
    db.close()

    if quote is None or not quote.spec_json or not quote.breakdown_json:
        raise HTTPException(status_code=404, detail="Quote not found or missing spec data")

    filename = export_quote_excel(quote.spec_json, quote.breakdown_json)
    return RedirectResponse(url=f"/download/exports/{filename}", status_code=303)


@router.get("/quotes/{quote_id}/export/formal")
def quote_export_formal(
    quote_id: int, user: Optional[User] = Depends(get_current_user_optional)
):
    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    db = SessionLocal()
    quote = db.query(QuoteHistory).filter(QuoteHistory.id == quote_id).first()
    db.close()

    if quote is None or not quote.spec_json or not quote.breakdown_json:
        raise HTTPException(status_code=404, detail="Quote not found or missing spec data")

    output_path = export_formal_quote(quote.spec_json, quote.breakdown_json)
    import os as _os
    filename = _os.path.basename(output_path)
    return RedirectResponse(url=f"/download/exports/{filename}", status_code=303)
```

Create `templates/quote_detail.html`:

```html
{% extends "base.html" %}
{% block title %}報價詳情 - PCB 報價系統{% endblock %}
{% block content %}
<h1 class="text-2xl font-semibold mb-2">報價詳情：{{ quote.quote_no or quote.id }}</h1>
<p class="text-sm text-slate-500 mb-6">
    建立者：{{ quote.created_by.email if quote.created_by else "-" }} ·
    最後修改：{{ quote.updated_by.email if quote.updated_by else "-" }}
</p>

<div class="grid grid-cols-1 md:grid-cols-2 gap-6">
    <div class="bg-white rounded-xl shadow p-6">
        <h2 class="font-medium mb-3">規格資訊</h2>
        <p>客戶：{{ quote.customer.company_name if quote.customer else "-" }}</p>
        <p>層數：{{ quote.layer }}L</p>
        <p>材料：{{ quote.material or "-" }}</p>
        <p>尺寸：{{ quote.length_mm or "-" }} x {{ quote.width_mm or "-" }} mm</p>
        <p>數量：{{ quote.qty }} pcs</p>
        <p>投料率：{{ quote.issue_ratio }}</p>
    </div>

    <div class="bg-white rounded-xl shadow p-6">
        <h2 class="font-medium mb-3">計價結果</h2>
        <p>總價：NT$ {{ "{:,.0f}".format(quote.total or 0) }}</p>
        <p>單片價格：NT$ {{ "{:,.2f}".format(quote.unit_price or 0) }}</p>
        {% if quote.breakdown_json and quote.breakdown_json.explanations %}
        <div class="mt-3 text-sm text-slate-600">
            {% for line in quote.breakdown_json.explanations %}
            <p>- {{ line }}</p>
            {% endfor %}
        </div>
        {% endif %}
    </div>
</div>

<div class="bg-white rounded-xl shadow p-6 mt-6">
    <h2 class="font-medium mb-3">狀態與備註</h2>
    <form method="post" action="/quotes/{{ quote.id }}/update" class="space-y-3">
        <select name="status" class="border border-slate-300 rounded-lg px-3 py-2 text-sm">
            {% for value, label in status_labels.items() %}
            <option value="{{ value }}" {% if quote.status == value %}selected{% endif %}>{{ label }}</option>
            {% endfor %}
        </select>
        <textarea name="notes" rows="3" class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" placeholder="內部備註">{{ quote.notes or "" }}</textarea>
        <button type="submit" class="bg-blue-600 text-white rounded-lg px-4 py-2 text-sm font-medium hover:bg-blue-700">
            儲存
        </button>
    </form>
</div>

<div class="mt-6 flex gap-3">
    <a href="/quotes/{{ quote.id }}/export/excel" class="bg-white border border-slate-300 rounded-lg px-4 py-2 text-sm font-medium hover:bg-slate-100">
        下載 Excel
    </a>
    <a href="/quotes/{{ quote.id }}/export/formal" class="bg-white border border-slate-300 rounded-lg px-4 py-2 text-sm font-medium hover:bg-slate-100">
        產生正式報價單
    </a>
</div>
{% endblock %}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_web_quote_detail.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add app/web.py templates/quote_detail.html tests/test_web_quote_detail.py
git commit -m "Add quote detail page with status/notes editing and export links"
```

---

### Task 11: Customers page

**Files:**
- Modify: `app/web.py`
- Create: `templates/customers.html`
- Test: `tests/test_web_customers.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_web_customers.py`:

```python
from fastapi.testclient import TestClient

from app.core.auth import hash_password


def _logged_in_client(temp_db):
    from app.main import app
    client = TestClient(app)
    db = temp_db.SessionLocal()
    user = temp_db.User(email="staff@example.com", password_hash=hash_password("hunter2"))
    db.add(user)
    db.commit()
    db.close()
    client.post("/login", data={"email": "staff@example.com", "password": "hunter2"})
    return client


def test_customers_list_and_create(temp_db):
    client = _logged_in_client(temp_db)

    response = client.post(
        "/customers",
        data={"company_name": "ABC Corp", "contact": "Jane", "phone": "0912345678", "email": "jane@abc.com"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    response = client.get("/customers")
    assert response.status_code == 200
    assert "ABC Corp" in response.text
    assert "Jane" in response.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_web_customers.py -v`
Expected: FAIL — 404 on `/customers`

- [ ] **Step 3: Write the implementation**

In `app/web.py`, add:

```python
@router.get("/customers", response_class=HTMLResponse)
def customers_list(
    request: Request, user: Optional[User] = Depends(get_current_user_optional)
):
    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    db = SessionLocal()
    customers = db.query(Customer).order_by(Customer.company_name).all()
    db.close()

    return templates.TemplateResponse(
        "customers.html", {"request": request, "user": user, "customers": customers}
    )


@router.post("/customers")
def customers_create(
    company_name: str = Form(...),
    contact: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
    user: Optional[User] = Depends(get_current_user_optional),
):
    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    db = SessionLocal()
    customer = Customer(
        company_name=company_name,
        contact=contact or None,
        phone=phone or None,
        email=email or None,
    )
    db.add(customer)
    db.commit()
    db.close()

    return RedirectResponse(url="/customers", status_code=303)
```

Create `templates/customers.html`:

```html
{% extends "base.html" %}
{% block title %}客戶管理 - PCB 報價系統{% endblock %}
{% block content %}
<h1 class="text-2xl font-semibold mb-6">客戶管理</h1>

<form method="post" action="/customers" class="bg-white rounded-xl shadow p-4 mb-6 flex flex-wrap gap-3 items-end">
    <div>
        <label class="block text-xs text-slate-500 mb-1">公司名稱</label>
        <input type="text" name="company_name" required class="border border-slate-300 rounded-lg px-3 py-1.5 text-sm">
    </div>
    <div>
        <label class="block text-xs text-slate-500 mb-1">聯絡人</label>
        <input type="text" name="contact" class="border border-slate-300 rounded-lg px-3 py-1.5 text-sm">
    </div>
    <div>
        <label class="block text-xs text-slate-500 mb-1">電話</label>
        <input type="text" name="phone" class="border border-slate-300 rounded-lg px-3 py-1.5 text-sm">
    </div>
    <div>
        <label class="block text-xs text-slate-500 mb-1">Email</label>
        <input type="email" name="email" class="border border-slate-300 rounded-lg px-3 py-1.5 text-sm">
    </div>
    <button type="submit" class="bg-blue-600 text-white rounded-lg px-4 py-1.5 text-sm font-medium hover:bg-blue-700">
        新增客戶
    </button>
</form>

<div class="bg-white rounded-xl shadow overflow-x-auto">
    <table class="w-full text-sm">
        <thead class="bg-slate-100 text-slate-600 text-left">
            <tr>
                <th class="px-4 py-2">公司名稱</th>
                <th class="px-4 py-2">聯絡人</th>
                <th class="px-4 py-2">電話</th>
                <th class="px-4 py-2">Email</th>
            </tr>
        </thead>
        <tbody>
            {% for c in customers %}
            <tr class="border-t border-slate-100">
                <td class="px-4 py-2">{{ c.company_name }}</td>
                <td class="px-4 py-2">{{ c.contact or "-" }}</td>
                <td class="px-4 py-2">{{ c.phone or "-" }}</td>
                <td class="px-4 py-2">{{ c.email or "-" }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endblock %}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_web_customers.py -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add app/web.py templates/customers.html tests/test_web_customers.py
git commit -m "Add customer list and creation page"
```

---

### Task 12: Stats page with charts

**Files:**
- Modify: `app/web.py`
- Create: `templates/stats.html`
- Test: `tests/test_web_stats.py`

**Interfaces:**
- Consumes: `app.core.database.{get_stats_by_layer, get_stats_by_material}` (added in Task 3).

- [ ] **Step 1: Write the failing test**

Create `tests/test_web_stats.py`:

```python
from fastapi.testclient import TestClient

from app.core.auth import hash_password


def _logged_in_client(temp_db):
    from app.main import app
    client = TestClient(app)
    db = temp_db.SessionLocal()
    user = temp_db.User(email="staff@example.com", password_hash=hash_password("hunter2"))
    db.add(user)
    db.commit()
    db.close()
    client.post("/login", data={"email": "staff@example.com", "password": "hunter2"})
    return client


def test_stats_page_loads_with_chart_data(temp_db):
    temp_db.save_quote("line:U1", {"layer": 6, "material": "FR4", "qty": 1}, {"status": "success", "total": 100.0, "unit_price": 100.0})

    client = _logged_in_client(temp_db)
    response = client.get("/stats")

    assert response.status_code == 200
    assert "chart.js" in response.text.lower() or "Chart.js" in response.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_web_stats.py -v`
Expected: FAIL — 404 on `/stats`

- [ ] **Step 3: Write the implementation**

In `app/web.py`, add import `from app.core.database import get_stats_by_layer, get_stats_by_material` (extend the existing import) and add:

```python
@router.get("/stats", response_class=HTMLResponse)
def stats_page(
    request: Request, user: Optional[User] = Depends(get_current_user_optional)
):
    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    return templates.TemplateResponse(
        "stats.html",
        {
            "request": request,
            "user": user,
            "by_layer": get_stats_by_layer(),
            "by_material": get_stats_by_material(),
        },
    )
```

Create `templates/stats.html`:

```html
{% extends "base.html" %}
{% block title %}統計報告 - PCB 報價系統{% endblock %}
{% block content %}
<h1 class="text-2xl font-semibold mb-6">統計報告</h1>

<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>

<div class="grid grid-cols-1 md:grid-cols-2 gap-6">
    <div class="bg-white rounded-xl shadow p-6">
        <h2 class="font-medium mb-3">層數分佈</h2>
        <canvas id="layerChart"></canvas>
    </div>
    <div class="bg-white rounded-xl shadow p-6">
        <h2 class="font-medium mb-3">材料分佈</h2>
        <canvas id="materialChart"></canvas>
    </div>
</div>

<script>
    const byLayer = {{ by_layer | tojson }};
    const byMaterial = {{ by_material | tojson }};

    new Chart(document.getElementById("layerChart"), {
        type: "bar",
        data: {
            labels: byLayer.map(r => r.layer + "L"),
            datasets: [{ label: "報價數", data: byLayer.map(r => r.count), backgroundColor: "#3B82F6" }],
        },
    });

    new Chart(document.getElementById("materialChart"), {
        type: "pie",
        data: {
            labels: byMaterial.map(r => r.material),
            datasets: [{ data: byMaterial.map(r => r.count), backgroundColor: ["#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6"] }],
        },
    });
</script>
{% endblock %}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_web_stats.py -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add app/web.py templates/stats.html tests/test_web_stats.py
git commit -m "Add stats page with layer/material distribution charts"
```

---

### Task 13: Require login on the existing JSON API

**Files:**
- Modify: `app/api.py`
- Test: `tests/test_api_auth.py`

**Interfaces:**
- Consumes: `app.web.get_current_user_optional` dependency.

- [ ] **Step 1: Write the failing test**

Create `tests/test_api_auth.py`:

```python
from fastapi.testclient import TestClient

from app.core.auth import hash_password


def test_api_requires_login(temp_db):
    from app.main import app
    client = TestClient(app)

    response = client.get("/api/quotes")
    assert response.status_code == 401


def test_api_works_when_logged_in(temp_db):
    from app.main import app
    client = TestClient(app)

    db = temp_db.SessionLocal()
    user = temp_db.User(email="staff@example.com", password_hash=hash_password("hunter2"))
    db.add(user)
    db.commit()
    db.close()

    client.post("/login", data={"email": "staff@example.com", "password": "hunter2"})
    response = client.get("/api/quotes")
    assert response.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_api_auth.py -v`
Expected: FAIL — `test_api_requires_login` gets 200 instead of 401 (no auth guard yet)

- [ ] **Step 3: Write the implementation**

In `app/api.py`, add near the top:

```python
from fastapi import Depends, HTTPException

from app.core.database import User
from app.web import get_current_user_optional


def require_user(user: User = Depends(get_current_user_optional)) -> User:
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user
```

Add `user: User = Depends(require_user)` as a parameter to every route function in `app/api.py` (`get_quotes`, `get_quote`, `update_quote`, `delete_quote`, `get_stats_summary`, `get_stats_by_layer`, `get_stats_by_material`). Example for the first one — apply the same pattern to the rest:

```python
@router.get("/quotes")
def get_quotes(
    start_date: str = Query(None),
    end_date: str = Query(None),
    layer: int = Query(None),
    material: str = Query(None),
    search: str = Query(None),
    limit: int = Query(100),
    user: User = Depends(require_user),
):
    ...
```

Also update `update_quote` to record who made the edit:

```python
@router.patch("/quotes/{quote_id}")
def update_quote(quote_id: int, data: dict, user: User = Depends(require_user)):
    try:
        db = SessionLocal()
        quote = db.query(QuoteHistory).filter(QuoteHistory.id == quote_id).first()

        if not quote:
            raise HTTPException(status_code=404, detail="報價不存在")

        if "total" in data:
            quote.total = data["total"]
        if "status" in data:
            quote.status = data["status"]
        if "notes" in data:
            quote.notes = data["notes"]
        quote.updated_by_user_id = user.id

        db.commit()
        db.close()

        return {"status": "success", "message": "報價已更新"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_api_auth.py -v`
Expected: 2 passed

- [ ] **Step 5: Run the full test suite to check for regressions**

Run: `pytest -v`
Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add app/api.py tests/test_api_auth.py
git commit -m "Require login on the JSON API and record who updates a quote"
```

---

### Task 14: Cross-channel parity test

**Files:**
- Test: `tests/test_quote_parity.py`

**Interfaces:**
- Consumes: `app.quote_engine.calculate_quote`, `app.core.database.save_quote`.

- [ ] **Step 1: Write the test**

Create `tests/test_quote_parity.py`:

```python
from app.quote_engine import calculate_quote


def test_same_spec_produces_same_total_regardless_of_channel(temp_db):
    """The web flow and the LINE flow must never diverge: both call
    calculate_quote() directly with no channel-specific business logic.
    This test proves saving the same spec from either channel produces
    an identical total, guarding against a future edit accidentally
    forking the calculation logic per-channel.
    """
    spec = {
        "layer": 6,
        "qty": 9,
        "material": "FR4",
        "length_mm": 100,
        "width_mm": 100,
        "enig": True,
        "enig_thickness_uinch": 10,
    }

    line_result = calculate_quote(spec)
    web_result = calculate_quote(spec)

    assert line_result["total"] == web_result["total"]

    temp_db.save_quote("line:U1", spec, line_result)
    temp_db.save_quote("web:1", spec, web_result, created_by_user_id=None)

    db = temp_db.SessionLocal()
    quotes = db.query(temp_db.QuoteHistory).order_by(temp_db.QuoteHistory.id).all()
    assert quotes[0].total == quotes[1].total
    db.close()
```

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest tests/test_quote_parity.py -v`
Expected: 1 passed (this test should pass immediately — it's a regression guard, not new behavior)

- [ ] **Step 3: Commit**

```bash
git add tests/test_quote_parity.py
git commit -m "Add regression test guarding LINE/web quote calculation parity"
```

---

### Task 15: Final wiring and manual smoke test

**Files:**
- Modify: `app/main.py` (confirm `web_router` mount from Task 5 is in place; no further code changes expected)

**Interfaces:** none new — this task is verification only.

- [ ] **Step 1: Run the full automated test suite**

Run: `pytest -v`
Expected: all tests pass, no warnings about missing templates/static files.

- [ ] **Step 2: Manual smoke test locally**

```bash
cp .env.example .env  # if not already present
python -c "from app.core.database import init_db; init_db()"
python scripts/create_user.py owner@example.com change-me-please
uvicorn app.main:app --reload --port 8000
```

Then in a browser:
1. Visit `http://localhost:8000/login`, sign in with the account just created.
2. Visit `/quotes/new`, fill in the structured form (e.g. layer 6, qty 9, material FR4, 100x100mm), submit, confirm it redirects to `/quotes` and the new row appears.
3. Open the quote's detail page, change status to 已批准, add a note, save, confirm it persists.
4. Visit `/customers`, add a customer, confirm it appears in the list and can be linked from `/quotes/new` via the company name field.
5. Visit `/stats`, confirm the two charts render.
6. Log out, confirm every page redirects to `/login`.

- [ ] **Step 3: Commit final plan checkbox updates**

```bash
git add docs/superpowers/plans/2026-07-22-web-quote-dashboard.md
git commit -m "Mark web quote dashboard implementation plan complete"
git push origin main
```
