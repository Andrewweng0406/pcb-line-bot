import os
import tempfile

import pytest


@pytest.fixture()
def temp_db(monkeypatch):
    """Point the app at a fresh, empty SQLite file for the duration of one test."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    # app.core.config's `settings` is a module-level singleton created once
    # at first import, so setting the env var alone doesn't affect it — the
    # singleton must be mutated directly. app.core.database then needs a
    # full reload so its `engine`/`SessionLocal` (built at import time from
    # `settings.DATABASE_URL`) point at the new file instead of Postgres.
    import importlib
    import app.core.config as config_module
    config_module.settings.DATABASE_URL = f"sqlite:///{db_path}"
    import app.core.database as database_module
    importlib.reload(database_module)
    database_module.init_db()

    yield database_module

    os.remove(db_path)
