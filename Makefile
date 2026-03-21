.PHONY: install dev run cli dashboard test clean docker-up docker-down lint format

install:
	pip install -e .

dev:
	pip install -e ".[dev,full]"

run: cli

cli:
	python -m ghost

dashboard:
	python -m ghost.backend.server

test:
	pytest tests/ -v --cov=ghost

lint:
	ruff check ghost/ tests/
	ruff format --check ghost/ tests/

format:
	ruff format ghost/ tests/

docker-up:
	docker-compose up -d --build

docker-down:
	docker-compose down

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache htmlcov *.egg-info dist build
