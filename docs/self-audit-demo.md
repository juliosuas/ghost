# Ghost self-audit demo

This is the safest public demo path for Ghost v2: an authorized self-audit with deterministic output and no external AI calls.

## Goal

Show that Ghost is becoming a defensible investigation case-file workspace, not just a collection script.

The demo should highlight:

- Local readiness checks.
- Explicit authorization/scope metadata.
- Deterministic `--no-ai` run.
- Stored case files.
- Report provenance.
- Case retrieval from SQLite.

## Script

```bash
# 1. Verify local setup
ghost doctor

# 2. Run an authorized deterministic self-audit demo
ghost investigate juliosuas \
  --type username \
  --modules username \
  --no-ai \
  --authorized \
  --scope "authorized self-audit demo" \
  --format json \
  --output demo-report.json

# 3. Show saved case files
ghost list

# 4. Open the saved case by ID prefix
ghost show <case-id-prefix>

# 5. Inspect report provenance
cat demo-report.json | jq '.provenance'
```

## Screenshot checklist

Capture these for README/demo material:

1. `ghost doctor` table.
2. Investigation progress running with `--no-ai --authorized`.
3. `ghost list` showing saved cases with scope and authorization.
4. `ghost show <id>` case summary with modules and graph size.
5. JSON provenance block from `demo-report.json`.

## Talk track

Ghost v2 is prioritizing trust before breadth. The demo should say:

> Ghost stores the investigation as a case file with scope, authorization, findings, provenance, and graph-ready entities. SQLite is the local default; Postgres comes later for team deployments.

Avoid demoing a random person. Use Julio's own public handle or another explicitly authorized test target.
