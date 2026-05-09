.PHONY: help build up down test test-load test-concurrent logs clean

help:
	@echo "NaijaPay Commands:"
	@echo "  make build          - Build all Docker images"
	@echo "  make up             - Start all services"
	@echo "  make down           - Stop all services"
	@echo "  make test           - Run unit and integration tests"
	@echo "  make test-concurrent - Run concurrent idempotency test (100 requests)"
	@echo "  make test-load      - Run load test (1000 requests)"
	@echo "  make logs           - View all service logs"
	@echo "  make clean          - Remove containers, volumes, and cache"

build:
	docker-compose build --no-cache

up:
	docker compose up -d
	@echo "Waiting for services to be ready..."
	sleep 5
	docker-compose ps

down:
	docker-compose down

test:
	docker-compose exec transaction-service pytest tests/ -v

test-concurrent:
	@echo "Running concurrent idempotency test..."
	docker-compose exec transaction-service python tests/test_idempotency.py

test-load:
	@echo "Running load test with 1000 requests..."
	docker-compose exec transaction-service python tests/test_load.py

logs:
	docker-compose logs -f

clean:
	docker-compose down -v
	docker system prune -f
	rm -rf services/*/__pycache__
	rm -rf services/*/app/__pycache__

dev-setup:
	pip install -r services/transaction-service/requirements.txt
	cp .env.example .env
	@echo "Development environment ready!"

redis-cli:
	docker-compose exec redis redis-cli

psql:
	docker-compose exec postgres psql -U naijapay -d naijapay