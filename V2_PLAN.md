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

## Gstack review integrated — 2026-05-03 heartbeat

### Office-hours forcing answers
- **Demand reality:** The first real feedback was not “add more sources”; it was “can this store data like a serious OSINT product?” That means trust/infrastructure is the current bottleneck.
- **Status quo:** Users can glue Sherlock/SpiderFoot/Maltego-style outputs, but the pain is fragmented evidence and weak investigation continuity.
- **Desperate specificity:** Security researchers and digital-footprint auditors need repeatable, defensible reports with provenance and graph state, not just a list of hits.
- **Narrowest wedge:** Authorized self-audit / client-owned asset audit. Safer, easier to demo, and better for public reputation.
- **Observation:** The repo had duplicate source trees and hidden import ambiguity. That is deadly for a Python security tool because tests can pass against the wrong package.
- **Future-fit:** v2 should become the “case file” layer: storage, graph, reports, provenance, then plugins.

### CEO verdict
Hold scope on new OSINT modules for this v2 sprint. Expand only where it increases trust: doctor command, storage clarity, provenance, and package hygiene. A flashy module launch with shaky internals would be bad taste. The 10-star product is a calm, defensible investigation workspace.

### Engineering verdict
The first batch is correct: canonical package cleanup + SQLite storage + tests. Next engineering risk is that `doctor` currently lives in CLI only; the same checks should become reusable functions later so API/server startup can share them.

## Batch 3 — report provenance

Added report provenance as the next trust primitive. Every generated JSON/HTML report now carries audit metadata: generation time, target/type/id, modules run, source URLs collected from findings, source URL count, module-level errors, and global errors.

Why this matters: Ghost should not just say “found things.” It should show where evidence came from, which modules ran, and what failed. That is the difference between a toy OSINT script and a defensible investigation case file.

## Batch 4 — deterministic demo mode

Added `--no-ai` to the root CLI and `ghost investigate`. This makes demos and CI-style investigations deterministic by forcing heuristic analysis even when `OPENAI_API_KEY` is present. It supports safer public demos and avoids accidental external AI calls during sensitive investigations.

Verified with:

```bash
ghost investigate demo_user --type username --modules social --no-ai --format json --output /tmp/ghost-demo-report.json
```

The generated JSON included fallback analysis and report provenance.

## Batch 5 — reusable doctor checks

Extracted doctor checks from CLI into `ghost.core.doctor`. The CLI still renders the table, but API/server startup and future CI can now reuse the same readiness logic without scraping terminal output.

This removes the next engineering smell from Batch 2: doctor is no longer trapped inside the UI layer.
