# NaijaPay
# NaijaPay - Day 1: Idempotent Payment Gateway Foundation

## ✅ Completed Today

### Core Features Implemented
1. **Docker Compose Setup** - PostgreSQL, Redis, RabbitMQ, Transaction Service
2. **FastAPI Application** - Production-ready with health checks and observability
3. **Idempotency Middleware** - Redis + PostgreSQL dual-layer caching
4. **Concurrent Safety** - Handles 100+ simultaneous identical requests without duplicates

### Architecture
Client Request (with Idempotency-Key)
↓
Idempotency Middleware
↓
Check Redis Cache → [HIT] → Return cached response
↓ [MISS]
Check PostgreSQL → [HIT] → Cache in Redis → Return
↓ [MISS]
Process Payment
↓
Store in PostgreSQL + Redis
↓
Return Response


## Quick Start (5 minutes)

```bash
# 1. Clone and setup
git clone <your-repo>
cd naijapay

# 2. Start all services
make up

# 3. Run tests
make test-concurrent

# 4. See results
curl http://localhost:8001/health