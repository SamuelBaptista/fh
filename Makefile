.PHONY: install test eval lint run dev up down

install:
	uv sync --all-extras

test:
	uv run pytest tests/unit -v

eval:
	uv run pytest tests/eval -v --tb=short

lint:
	uv run ruff check app/ tests/
	uv run ruff format --check app/ tests/

format:
	uv run ruff format app/ tests/

run:
	uv run uvicorn app.api.routes:app --host 0.0.0.0 --port 8000 --reload

up:
	docker compose up -d

down:
	docker compose down -v
