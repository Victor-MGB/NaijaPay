from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

import structlog
from prometheus_fastapi_instrumentator import Instrumentator
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from .api.payment_router import router as payments_router
from .api.health_router import router as health_router

from .middleware.idempotency import IdempotencyMiddleware
from .utils.redis_client import redis_client
from .utils.database import db_pool
from .utils.queue import rabbitmq_client

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up Transaction Service...")
    await db_pool.initialize()
    await redis_client.initialize()
    await rabbitmq_client.initialize()
    logger.info("All connections initialized successfully")

    yield

    logger.info("Shutting down Transaction Service...")
    await db_pool.close()
    await redis_client.close()
    await rabbitmq_client.close()
    logger.info("All connections closed successfully")


app = FastAPI(
    title="Naija Transaction Service",
    description="A resilient payment microservice with idempotency for handling transactions in the Naija ecosystem.",
    version="1.0.0",
    lifespan=lifespan,
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],           # Change this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(IdempotencyMiddleware)

# Instrumentation
Instrumentator().instrument(app).expose(app)
FastAPIInstrumentor.instrument_app(app)

# Routes
app.include_router(health_router, prefix="/health", tags=["health"])
app.include_router(payments_router, prefix="/api/v1/payments", tags=["payments"])


# Exception Handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    logger.error(
        f"HTTPException occurred: {exc.detail}",
        status_code=exc.status_code
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code
        },
    )