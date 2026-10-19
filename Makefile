.PHONY: help up down restart logs sync migrate seed clean-db reset-db test lint run scrape

help:
	@echo "Vistarae Developer Shortcuts (powered by uv):"
	@echo "  make sync     - Sync dependencies and editable packages with uv"
	@echo "  make up       - Start PostGIS, Jaeger, and background services"
	@echo "  make down     - Stop all running services"
	@echo "  make restart  - Restart all services"
	@echo "  make logs     - Tail logs across services"
	@echo "  make migrate  - Run Alembic schema migrations via uv"
	@echo "  make seed     - Seed local database via uv"
	@echo "  make test     - Run pytest suite with coverage via uv"
	@echo "  make lint     - Run code quality checks via uv"
	@echo "  make run      - Start local development gateway via uv"
	@echo "  make scrape   - Run photo scraper tool via uv"

sync:
	uv sync

up:
	docker compose up -d

down:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f

migrate:
	uv run alembic upgrade head

seed:
	uv run python scripts/seed_local_db.py

clean-db:
	docker compose exec -T db psql -U postgres -d vistarae -c "TRUNCATE pois, poi_access_points, poi_list_memberships, lists, user_tags, idempotency_keys, user_quotas, user_metrics, user_preferences, users CASCADE;"

reset-db:
	docker compose exec -T db psql -U postgres -d vistarae -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
	$(MAKE) migrate

test:
	uv run pytest -v

lint:
	uv run ruff check .

run:
	uv run uvicorn services.local_gateway:app --reload --port 8030

scrape:
	uv run python photo_scraper/main.py

