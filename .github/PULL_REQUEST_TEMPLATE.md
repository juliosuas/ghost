## What changed

-

## Why

-

## Checklist

- [ ] Tests pass (`python -m pytest -q`)
- [ ] Ruff is clean (`python -m ruff check ghost tests conftest.py` and `python -m ruff format --check ghost tests conftest.py`)
- [ ] Fixtures and examples are synthetic only (`demo_user` or other invented data; never real people)
- [ ] No network calls in parsers, and no new scraping modules or network parsers
- [ ] Docs updated when behavior, setup, or policy changed

## Safety

- [ ] This supports authorized investigations or self-audits only
- [ ] No private target data, secrets, generated databases, reports, or investigation artifacts are committed
- [ ] No telemetry and no auto-update
