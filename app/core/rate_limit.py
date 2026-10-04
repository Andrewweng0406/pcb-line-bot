import hashlib
import math
import threading
import time

import redis
from fastapi import HTTPException

from app.core.config import settings


class RateLimiter:
    def __init__(self):
        self._entries = {}
        self._lock = threading.Lock()

    def clear_local(self):
        with self._lock:
            self._entries.clear()

    def consume(self, scope, identity, limit, window=60):
        if limit < 1 or window < 1:
            raise HTTPException(status_code=503, detail="Rate limiter is not configured correctly")
        key = "pcb:rate:" + hashlib.sha256(f"{scope}:{identity}".encode()).hexdigest()
        if settings.REDIS_ENABLED:
            try:
                client = redis.from_url(settings.REDIS_URL, socket_timeout=2, socket_connect_timeout=2)
                try:
                    # Increment and expiry must be atomic across workers.
                    count, remaining = client.eval(
                        "local n = redis.call('INCR', KEYS[1]); "
                        "if n == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]); end; "
                        "return {n, redis.call('TTL', KEYS[1])}",
                        1, key, window,
                    )
                finally:
                    client.close()
            except redis.RedisError:
                raise HTTPException(status_code=503, detail="Rate limiting temporarily unavailable. Try again later.")
        else:
            now = time.monotonic()
            with self._lock:
                if key not in self._entries and len(self._entries) >= 10000:
                    self._entries = {k: v for k, v in self._entries.items() if v[1] > now}
                    if len(self._entries) >= 10000:
                        raise HTTPException(status_code=503, detail="Rate limiting temporarily unavailable")
                count, deadline = self._entries.get(key, (0, now + window))
                if deadline <= now:
                    count, deadline = 0, now + window
                count += 1
                self._entries[key] = (count, deadline)
                remaining = max(1, math.ceil(deadline - now))
        if count > limit:
            raise HTTPException(status_code=429, detail="Too many requests. Try again later.", headers={"Retry-After": str(max(1, remaining))})


rate_limiter = RateLimiter()


def client_identity(request):
    # Do not trust arbitrary X-Forwarded-For headers. Uvicorn must trust only
    # the deployment's proxy when resolving request.client.
    return request.client.host if request.client else "unknown"
