import json
import redis
from typing import Dict, Optional
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class MemoryStore:
    def __init__(self):
        self.redis_enabled = settings.REDIS_ENABLED
        self.local_memory: Dict[str, Dict] = {}

        if self.redis_enabled:
            try:
                self.redis_client = redis.from_url(settings.REDIS_URL)
                self.redis_client.ping()
                logger.info("Redis connection established")
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}, falling back to local memory")
                self.redis_enabled = False
        else:
            self.redis_client = None

    def get(self, user_id: str) -> Optional[Dict]:
        try:
            if self.redis_enabled:
                data = self.redis_client.get(f"user:{user_id}")
                if data:
                    return json.loads(data)
                return None
            else:
                return self.local_memory.get(user_id)
        except Exception as e:
            logger.error(f"Error getting memory for {user_id}: {e}")
            return self.local_memory.get(user_id)

    def set(self, user_id: str, data: Dict, ttl: int = 86400):
        try:
            if self.redis_enabled:
                self.redis_client.setex(
                    f"user:{user_id}",
                    ttl,
                    json.dumps(data)
                )
            else:
                self.local_memory[user_id] = data
            logger.debug(f"Memory updated for {user_id}")
        except Exception as e:
            logger.error(f"Error setting memory for {user_id}: {e}")
            self.local_memory[user_id] = data

    def delete(self, user_id: str):
        try:
            if self.redis_enabled:
                self.redis_client.delete(f"user:{user_id}")
            else:
                self.local_memory.pop(user_id, None)
            logger.debug(f"Memory cleared for {user_id}")
        except Exception as e:
            logger.error(f"Error deleting memory for {user_id}: {e}")
            self.local_memory.pop(user_id, None)

    def __contains__(self, user_id: str) -> bool:
        try:
            if self.redis_enabled:
                return self.redis_client.exists(f"user:{user_id}") > 0
            else:
                return user_id in self.local_memory
        except Exception as e:
            logger.error(f"Error checking memory for {user_id}: {e}")
            return user_id in self.local_memory


user_memory = MemoryStore()
