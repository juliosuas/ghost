# Ghost v2 Plan

## Gstack diagnosis

Ghost v1 has the right surface area, but v2 must become trustworthy before it becomes bigger. The highest-ROI path is not “more OSINT modules”; it is making the investigation engine reliable, auditable, and shippable.

## Feedback reviewed

GitHub issue #1 feedback raised a real concern: JSON-file style persistence does not scale for an OSINT product that stores investigations, entities, relationships, and reports. The repo already had a SQLite database layer, but v2 needed to make that direction explicit, configurable, indexed, and documented.

## v2 priorities

1. **Reliability first**
   - One canonical Python package only: `ghost/`.
   - Remove legacy duplicate top-level packages that caused import ambiguity.
   - Keep tests green from editable installs and module execution.

2. **Durable investigation storage**
   - SQLite as the supported v2 default.
   - `DATABASE_URL` path resolution.
   - Schema version marker and query indexes.
   - Explicit failure for unsupported DB schemes so deployments do not silently write to the wrong place.

3. **Investigation quality**
   - Better username module accuracy: platform-specific redirect handling and case preservation.
   - Safer module errors and clearer report outputs.
   - Add consent/scope language in UX before broader automation.

4. **Product wedge**
   - Position Ghost as a defensive investigation workspace for authorized security research, journalism, and personal digital footprint audits.
   - Avoid adding invasive/stalking-oriented features.
   - Next public demo should show an authorized self-audit, not targeting a random person.

## First implementation batch

Completed in branch `v2-feedback-database-and-cli-polish`:

- Removed legacy duplicate top-level packages (`ai/`, `backend/`, `core/`, `modules/`, `ui/`, root `__init__.py`) so `ghost/` is the only source package.
- Added SQLite `DATABASE_URL` resolver, schema version marker, DB parent creation, busy timeout, and additional indexes.
- Documented storage in README and `.env.example`.
- Updated tests for username redirect metadata and case preservation.
- Cleaned lint issues surfaced by Ruff.

## Next batch

1. Add CLI `ghost doctor` to validate DB path, API keys, optional dependencies, and module availability.
2. Add `--offline` / `--no-ai` profile for safe demos and deterministic tests.
3. Add report provenance: timestamp, module list, source URLs, errors, and confidence per finding.
4. Add GitHub issue response summarizing SQLite direction and Postgres roadmap.
