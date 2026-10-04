from concurrent.futures import ThreadPoolExecutor

import pytest
import redis
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.rate_limit import RateLimiter
from app.core.config import settings


def test_local_limiter_is_thread_safe_and_resets_after_window(monkeypatch):
    import app.core.rate_limit as module
    monkeypatch.setattr(settings, "REDIS_ENABLED", False)
    monkeypatch.setattr(module.time, "monotonic", lambda: 100)
    limiter = RateLimiter()
    def consume():
        try:
            limiter.consume("ai", "user1", 3)
            return True
        except HTTPException as exc:
            assert exc.status_code == 429 and exc.headers["Retry-After"] == "60"
            return False
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(lambda _: consume(), range(10))) == 3
    limiter.consume("ai", "user2", 3)
    monkeypatch.setattr(module.time, "monotonic", lambda: 160)
    limiter.consume("ai", "user1", 3)


def test_redis_limiter_uses_atomic_expiring_counter_and_fails_closed(monkeypatch):
    import app.core.rate_limit as module
    monkeypatch.setattr(settings, "REDIS_ENABLED", True)
    calls = []
    class Client:
        def eval(self, script, count, key, window):
            calls.append((script, count, key, window))
            return [2, 30]
        def close(self):
            pass
    monkeypatch.setattr(module.redis, "from_url", lambda *args, **kwargs: Client())
    limiter = RateLimiter()
    with pytest.raises(HTTPException) as error:
        limiter.consume("login", "sensitive-ip", 1)
    assert error.value.status_code == 429
    assert error.value.headers["Retry-After"] == "30"
    assert "sensitive-ip" not in calls[0][2] and "EXPIRE" in calls[0][0]
    def unavailable(*args, **kwargs):
        raise redis.ConnectionError("offline")
    monkeypatch.setattr(module.redis, "from_url", unavailable)
    with pytest.raises(HTTPException) as error:
        limiter.consume("ai", "1", 10)
    assert error.value.status_code == 503


def test_login_and_ai_endpoints_are_throttled(temp_db, monkeypatch):
    from app.main import app
    from app.core.auth import hash_password
    import app.web as web
    monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT", 2)
    monkeypatch.setattr(settings, "AI_RATE_LIMIT", 1)
    monkeypatch.setattr(settings, "REDIS_ENABLED", False)
    with temp_db.SessionLocal() as session:
        session.add(temp_db.User(email="rate@example.com", password_hash=hash_password("test-password")))
        session.commit()
    client = TestClient(app)
    assert client.post("/login", data={"email": "rate@example.com", "password": "wrong"}).status_code == 401
    assert client.post("/login", data={"email": "rate@example.com", "password": "test-password"}).status_code == 200
    assert client.post("/login", data={"email": "rate@example.com", "password": "wrong"}).status_code == 429
    monkeypatch.setattr(web, "parse_pcb_text", lambda text: {"layer": 6, "qty": 10})
    assert client.post("/quotes/new/ai-assist", data={"spec_text": "6L qty10"}).status_code == 200
    assert client.get("/quote_text", params={"text": "6L"}).status_code == 429
