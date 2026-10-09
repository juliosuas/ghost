# Contributing to Ghost

Ghost is a local case-file tool for authorized investigations and self-audits. Read [ACCEPTABLE_USE.md](ACCEPTABLE_USE.md) and the [code of conduct](CODE_OF_CONDUCT.md) before you open an issue or a pull request.

Report security problems privately. See [SECURITY.md](SECURITY.md). Do not file them as public issues.

## Development setup

Python 3.10 or newer.

```bash
git clone https://github.com/juliosuas/ghost.git
cd ghost
python3 -m pip install -e ".[dev]"
```

That extra matches CI (pytest and ruff). `make dev` also installs the optional `full` extra. Use `.[dev]` unless you are working on an optional dependency.

Copy `.env.example` to `.env` only when you need local keys. Do not commit `.env`, databases, or generated reports.

The supported CLI entrypoint is `python3 -m ghost`.

## Ruff and pytest

Run the same checks CI runs (`.github/workflows/ci.yml`):

```bash
python -m ruff check ghost tests conftest.py
python -m ruff format --check ghost tests conftest.py
python -m pytest -q
```

`make lint` checks `ghost/` and `tests/` only. Include `conftest.py` so you match CI. `make test` adds coverage; CI uses `python -m pytest -q`.

## Pull request checklist

The template in [`.github/PULL_REQUEST_TEMPLATE.md`](.github/PULL_REQUEST_TEMPLATE.md) is the checklist. Before you open a PR:

- Tests pass (`python -m pytest -q`).
- Ruff check and format check pass.
- Fixtures are synthetic.
- Parsers do not make network calls.
- Docs are updated when behavior, setup, or policy changes.

## Synthetic fixtures only

Examples, tests, issues, and pull requests use synthetic data. The canonical handle is `demo_user`. Invented placeholders such as `alex.rivera.demo@example.com` are fine. Never commit or paste data about a real person: real names, emails, phone numbers, photos, or investigation reports.

Shipped samples live in [`examples/`](examples/).

## No new scraping modules or network parsers

Do not add modules that scrape sites, probe accounts, or parse live network responses. New collection code is out of scope.

An offline ingest parser that reads another tool's saved output may be proposed with the [New ingest parser](.github/ISSUE_TEMPLATE/new_ingest_parser.yml) issue form. It must include a synthetic fixture and must not perform network I/O.

## Out of scope

- Telemetry
- Auto-update
- Private target data in the repository

## Labels to create

Create these labels in the GitHub repository settings (Settings → Labels). Do not create them through the API:

| Label | Use |
|---|---|
| `good first issue` | Small, scoped tasks for a new contributor |
| `help wanted` | Work the maintainer wants help with |
| `parser` | Offline ingest parser requests |
| `security` | Public tracking only after a private report, when a public issue is appropriate |

Issue forms also apply `bug`, `enhancement`, `documentation`, `question`, and `good first issue` when those labels exist. Create any of them that are missing in the same settings screen, still without using the API.
