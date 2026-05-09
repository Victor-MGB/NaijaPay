import redis.asyncio as redis
from typing import Optional
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from app.core.config import settings


logger = structlog.get_logger()


class RedisClient:
    _instance: Optional['RedisClient'] = None
    _client: Optional[redis.Redis] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def initialize(self):
        """Initialize Redis connection pool"""
        if self._client:
            return  

        try:
            self._client = redis.from_url(
                settings.REDIS_URL,
                max_connections=50,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30,   
            )
            logger.info("Redis connection established")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    async def ping(self) -> bool:
        """Health check ping - used by your monitoring"""
        if not self._client:
            await self.initialize()
        
        try:
            return await self._client.ping()
        except Exception as e:
            logger.warning(f"Redis ping failed: {e}")
            return False

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=3),
        retry=retry_if_exception_type((ConnectionError, TimeoutError, redis.ConnectionError))
    )
    async def get(self, key: str) -> Optional[str]:
        if not self._client:
            await self.initialize()
        return await self._client.get(key)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=3),
        retry=retry_if_exception_type((ConnectionError, TimeoutError, redis.ConnectionError))
    )
    async def setex(self, key: str, ttl: int, value: str) -> bool:
        if not self._client:
            await self.initialize()
        return await self._client.setex(key, ttl, value)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=3),
        retry=retry_if_exception_type((ConnectionError, TimeoutError, redis.ConnectionError))
    )
    async def delete(self, key: str) -> int:
        if not self._client:
            await self.initialize()
        return await self._client.delete(key)

    async def close(self):
        if self._client:
            await self._client.close()
            self._client = None
            logger.info("Redis connection closed")


# Singleton instance
redis_client = RedisClient()