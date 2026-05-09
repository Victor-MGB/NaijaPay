from fastapi import APIRouter
from typing import Dict, Any
import structlog

from ..utils.redis_client import redis_client
from ..utils.database import db_pool

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.get("")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint"""
    status = {
        "service": "transaction-service",
        "status": "healthy",
        "checks": {}
    }

    # Check Redis
    try:
        redis_healthy = await redis_client.ping()
        status["checks"]["redis"] = "healthy" if redis_healthy else "unhealthy"
        if not redis_healthy:
            status["status"] = "degraded"
    except Exception as e:
        status["checks"]["redis"] = f"unhealthy: {str(e)}"
        status["status"] = "degraded"

    # Check Database
    try:
        db_healthy = await db_pool.ping()                    
        status["checks"]["database"] = "healthy" if db_healthy else "unhealthy"
        if not db_healthy:
            status["status"] = "degraded"
    except Exception as e:
        status["checks"]["database"] = f"unhealthy: {str(e)}"
        status["status"] = "degraded"

    return status


@router.get("/ready")
async def readiness_check() -> Dict[str, Any]:
    """Readiness probe endpoint"""
    issues = []

    # Check Redis
    try:
        if not await redis_client.ping():
            issues.append("Redis is not healthy")
    except Exception as e:
        issues.append(f"Redis: {e}")

    # Check Database
    try:
        if not await db_pool.ping():                         
            issues.append("Database is not healthy")
    except Exception as e:
        issues.append(f"Database: {e}")

    return {
        "ready": len(issues) == 0,
        "issues": issues if issues else None
    }