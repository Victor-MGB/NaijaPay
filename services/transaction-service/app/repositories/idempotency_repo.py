import json
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import structlog

from ..utils.redis_client import redis_client
from ..utils.database import db_pool

logger = structlog.get_logger(__name__)


class IdempotencyRepository:
    """Repository for idempotency operations with Redis + PostgreSQL fallback"""
    
    def __init__(self, ttl_seconds: int = 3600):
        self.ttl = ttl_seconds

    async def get_cached_response(self, idempotency_key: str) -> Optional[Dict[str, Any]]:
        """Get cached response from Redis first, then PostgreSQL"""
        try:
            # Try Redis first
            cached = await redis_client.get(f"idempotent:{idempotency_key}")
            if cached:
                logger.info("Cache hit in Redis", key=idempotency_key)
                try:
                    data = json.loads(cached)
                    if isinstance(data, dict):
                        return data
                    else:
                        logger.warning("Invalid cached data format", key=idempotency_key)
                        return None
                except json.JSONDecodeError:
                    logger.warning("Failed to parse Redis cache", key=idempotency_key)
                    return None

            # Fallback to PostgreSQL
            async with db_pool.connection() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT response_data 
                    FROM idempotent_requests 
                    WHERE idempotency_key = $1 AND expires_at > NOW()
                    """,
                    idempotency_key
                )
                if row and row["response_data"]:
                    logger.info("Cache hit in PostgreSQL", key=idempotency_key)
                    return row["response_data"]

            logger.info("Cache miss", key=idempotency_key)
            return None

        except Exception as e:
            logger.error("Failed to get cached response", key=idempotency_key, error=str(e))
            return None

    async def store_response(
        self, 
        idempotency_key: str, 
        response_data: Dict[str, Any], 
        status_code: int
    ) -> None:
        """Store response in both Redis and PostgreSQL"""
        expires_at = datetime.utcnow() + timedelta(seconds=self.ttl)
        
        try:
            serializable_data = self._make_json_serializable(response_data)
            
            async with db_pool.connection() as conn:
                await conn.execute(
                    """
                    INSERT INTO idempotent_requests 
                        (idempotency_key, response_data, status_code, expires_at)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (idempotency_key) 
                    DO UPDATE
                    SET response_data = EXCLUDED.response_data,
                        status_code = EXCLUDED.status_code,
                        expires_at = EXCLUDED.expires_at,
                        updated_at = NOW()
                    """,
                    idempotency_key,
                    json.dumps(serializable_data),
                    status_code,
                    expires_at
                )

            await redis_client.setex(
                f"idempotent:{idempotency_key}",
                self.ttl,
                json.dumps(serializable_data)
            )
            
            logger.info("Idempotent response stored successfully", key=idempotency_key)
            
        except Exception as e:
            logger.error("Failed to store idempotent response", key=idempotency_key, error=str(e))
            raise

    def _make_json_serializable(self, data: Any) -> Any:
        """Recursively convert datetime objects to ISO strings"""
        if isinstance(data, datetime):
            return data.isoformat()
        elif isinstance(data, dict):
            return {k: self._make_json_serializable(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._make_json_serializable(item) for item in data]
        else:
            return data