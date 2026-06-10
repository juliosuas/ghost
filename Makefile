PYTHON ?= python

.PHONY: install dev run cli dashboard test clean docker-up docker-down lint format

install:
	$(PYTHON) -m pip install -e .

dev:
	$(PYTHON) -m pip install -e ".[dev,full]"

run: cli

cli:
	$(PYTHON) -m ghost

dashboard:
	$(PYTHON) -m ghost.backend.server

test:
	$(PYTHON) -m pytest tests/ -v --cov=ghost

lint:
	$(PYTHON) -m ruff check ghost/ tests/
	$(PYTHON) -m ruff format --check ghost/ tests/

format:
	$(PYTHON) -m ruff format ghost/ tests/

docker-up:
	docker-compose up -d --build

docker-down:
	docker-compose down

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache htmlcov *.egg-info dist build
