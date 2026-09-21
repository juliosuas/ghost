# Changelog

Ghost follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [Semantic Versioning](https://semver.org/).

The package version in `pyproject.toml` is **0.1.0**. There is no GitHub release tag yet. **The next tag should be `v0.1.0`.** When that release is cut, move the items below under `## [0.1.0] - YYYY-MM-DD` and leave `## [Unreleased]` empty (or with post-tag work only).

## [Unreleased]

### Added

- `ghost doctor` / `ghost doctor --json` fail closed on insecure server defaults: missing or placeholder `GHOST_SECRET_KEY`, non-loopback `GHOST_HOST`, empty `GHOST_API_TOKEN`. CLI-only `investigate --authorized --no-ai` is unchanged and does not start Flask.
- `.env.example` documents the locked names `GHOST_SECRET_KEY`, `GHOST_HOST`, and `GHOST_API_TOKEN`.
- 60-second Quick Start in the README using copy-paste commands that match the real CLI (`python3 -m pip install -e .`, `python3 -m ghost doctor`, `python3 -m ghost investigate … --no-ai --authorized`).
- Honest Ghost vs maigret comparison in Why Ghost (case files, provenance, multi-vector vs username-hunter coverage).
- Synthetic sample case and report snippet under `examples/` (fake usernames/emails only).
- Issue templates for good first issues and docs/questions.
- Screenshot placeholder path `docs/screenshots/demo.gif` documented in `docs/screenshots/README.md` (GIF not committed).

### Changed

- README positioning: local authorized case files + provenance, not "AI-Powered Platform." Social and darkweb modules marked experimental / not Quick Start defaults.
- Ruff lint `select` pinned to the historical default (`E4`, `E7`, `E9`, `F`) so CI is not blocked by Ruff 0.12+ expanding rules on an unchanged codebase (this was the #12 main failure; kept from #13).

- README install path: editable source install is supported; `pip install ghost-osint` is marked unpublished (PyPI 404).
- README claims calibrated to the current CLI: OpenAI is optional, dashboard HTML is not shipped, PDF needs `weasyprint`, username coverage is 70 built-in HTTP checks plus optional Sherlock.

### Notes for the next tag

- Tag **`v0.1.0`** from `main` after this docs work lands, matching `ghost/__init__.py` and `pyproject.toml`.
- Do not treat this changelog entry as a behavior-breaking CLI release; it is discoverability and contributor onboarding.
