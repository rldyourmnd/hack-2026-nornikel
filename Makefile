.PHONY: install test lint typecheck api web demo eval generate-fixtures docker-up docker-down ci reindex warmup

install:
	uv sync --group dev
	cd apps/web && npm install

lint:
	uv run ruff check .
	cd apps/web && npm run lint

typecheck:
	uv run mypy
	cd apps/web && npm run typecheck

test:
	uv run pytest

api:
	uv run fastapi dev services/api/main.py --host 0.0.0.0 --port 8000

web:
	cd apps/web && npm run dev -- --host 0.0.0.0 --port 5173

generate-fixtures:
	uv run --extra fixtures python scripts/generate_synthetic_docs.py

eval:
	uv run python scripts/run_eval.py

eval-realcase:
	uv run python scripts/run_realcase_eval.py

reindex:
	uv run python scripts/reindex.py

warmup:
	uv run python scripts/warmup.py

docker-up:
	docker compose up --build

docker-down:
	docker compose down

demo: docker-up

ci: lint typecheck test
	cd apps/web && npm run build
