.PHONY: help up down restart logs migrate seed test lint

help:
	@echo "Vistarae Developer Shortcuts:"
	@echo "  make up       - Start PostGIS, Jaeger, and FastAPI services"
	@echo "  make down     - Stop all running services"
	@echo "  make restart  - Restart all services"
	@echo "  make logs     - Tail logs across services"
	@echo "  make migrate  - Execute SQL migrations against active database"
	@echo "  make seed     - Seed database with sample POIs and lists"
	@echo "  make test     - Run backend pytest suite"
	@echo "  make lint     - Run code quality and formatting checks"

up:
	docker compose up -d

down:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f

migrate:
	docker compose exec -T db psql -U postgres -d vistarae -f /docker-entrypoint-initdb.d/20261001_init_postgis.sql
	docker compose exec -T db psql -U postgres -d vistarae -f /docker-entrypoint-initdb.d/20261002_create_pois_and_access_points.sql
	docker compose exec -T db psql -U postgres -d vistarae -f /docker-entrypoint-initdb.d/20261003_create_lists_and_geocache.sql
	docker compose exec -T db psql -U postgres -d vistarae -f /docker-entrypoint-initdb.d/20261004_create_users_and_add_user_id.sql

seed:
	docker compose exec -T db psql -U postgres -d vistarae -f /app/../supabase/seed.sql

test:
	cd backend && pytest -v

lint:
	cd backend && ruff check .
