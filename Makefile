.PHONY: help build up down logs clean test dev playwright-install

help:
	@echo "Available commands:"
	@echo "  make build              - Build all Docker images"
	@echo "  make up                 - Start all services in detached mode"
	@echo "  make down               - Stop all services"
	@echo "  make logs               - Follow logs from all services"
	@echo "  make clean              - Remove all containers, volumes, and images"
	@echo "  make test               - Run test suite"
	@echo "  make dev                - Run scraper locally (requires poetry)"
	@echo "  make playwright-install - Install Playwright browsers locally"

build:
	docker-compose build

up:
	docker-compose up -d --build

down:
	docker-compose down

logs:
	docker-compose logs -f

clean:
	docker-compose down -v
	docker rmi pandarank-scraper pandarank-api postgres:16-alpine || true
	rm -rf scraper/artifacts/

test:
	cd scraper && python -m pytest tests/ -v

dev:
	cd scraper && python -m app.main

playwright-install:
	cd scraper && playwright install chromium

# Database commands
db-shell:
	docker-compose exec db psql -U scraper -d chatlogs

db-backup:
	docker-compose exec db pg_dump -U scraper chatlogs > backup_$(shell date +%Y%m%d_%H%M%S).sql

# Individual service commands
scraper-logs:
	docker-compose logs -f scraper

api-logs:
	docker-compose logs -f api

api-docs:
	@echo "API documentation available at http://localhost:8000/docs"

# Health checks
health-check:
	@curl -s http://localhost:8080/metrics | grep "chatgpt_scrapes_total" || echo "Scraper metrics not available"
	@curl -s http://localhost:8000/ | jq . || echo "API not available"