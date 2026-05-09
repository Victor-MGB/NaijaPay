import asyncpg
from typing import Optional, AsyncIterator
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential
from contextlib import asynccontextmanager

from app.core.config import settings

logger = structlog.get_logger(__name__)


class DatabasePool:
    _pool: Optional[asyncpg.Pool] = None

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=1, max=10), reraise=True)
    async def initialize(self):
        if self._pool is not None:
            return

        try:
            self._pool = await asyncpg.create_pool(
                dsn=settings.DATABASE_URL,
                min_size=5,
                max_size=20,
                command_timeout=60,
                max_queries=50000,
                max_inactive_connection_lifetime=300,
                timeout=30,
            )
            logger.info("Database pool created successfully")
            await self.ping()
            logger.info("Database connection verified")
        except Exception as e:
            logger.error(f"Failed to initialize database pool: {e}")
            raise

    async def ping(self) -> bool:
        if not self._pool:
            await self.initialize()
        try:
            async with self._pool.acquire() as conn:
                await conn.execute("SELECT 1")
            return True
        except Exception as e:
            logger.warning(f"Database ping failed: {e}")
            return False

    @asynccontextmanager
    async def connection(self) -> AsyncIterator[asyncpg.Connection]:
        """Proper async context manager - THIS IS THE KEY FIX"""
        if not self._pool:
            await self.initialize()

        conn = await self._pool.acquire()
        try:
            yield conn
        finally:
            await self._pool.release(conn)

    # Keep for backward compatibility
    async def acquire(self):
        if not self._pool:
            await self.initialize()
        return await self._pool.acquire()

    async def release(self, conn):
        if self._pool and conn:
            await self._pool.release(conn)

    async def close(self):
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("Database pool closed")


db_pool = DatabasePool()