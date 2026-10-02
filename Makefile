.PHONY: dev check test

dev:
	docker compose up --build

check:
	ruff check .
	mypy .
	pytest
	cd frontend && npm run lint
	cd frontend && npm run build

test:
	pytest
