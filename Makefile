.PHONY: install test eval lint format run up down logs

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

logs:
	@echo "Fetching latest CloudWatch logs from deployed service..."
	@mkdir -p runs
	@aws logs filter-log-events \
		--log-group-name "/ecs/watchtower-mini" \
		--start-time $$(date -d "10 minutes ago" +%s000 2>/dev/null || date -v-10M +%s000) \
		--region us-east-1 \
		--output text | grep -v "GET /health" | grep -v "^SEARCH" | grep -v "^EVENTS" | grep -v "^$$" | tee runs/deployed-run-evidence.log
	@echo ""
	@echo "Saved to runs/deployed-run-evidence.log"
