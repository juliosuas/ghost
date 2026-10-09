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
# On a fresh clone, doctor exits 1 until GHOST_SECRET_KEY and GHOST_API_TOKEN
# are set (and GHOST_HOST, if set, is 127.0.0.1 or localhost). That is an
# exposure gate. The same run creates the SQLite schema, which `ghost import`
# needs. CLI investigate below does not start Flask and still works.
ghost doctor
ghost doctor --json

# 2. Run an authorized deterministic self-audit demo.
# This writes demo-report.json. It does not insert the SQLite row.
ghost investigate YOUR_HANDLE \
    --type username \
    --modules username \
    --no-ai \
    --authorized \
    --scope "authorized self-audit demo" \
    --format json \
    --output demo-report.json

# 3. Store that report as a case, then list it
ghost import demo-report.json
ghost list

# 4. Open the saved case by ID prefix
ghost show <case-id-prefix>

# 5. Export a portable case file for handoff or backup
ghost export <case-id-prefix> --output demo-case.json

# 6. Inspect report provenance
cat demo-report.json | jq '.provenance'
```

## Screenshot checklist

Capture these for README/demo material:

1. `ghost doctor` table.
2. `ghost doctor --json` readiness output.
3. Investigation progress running with `--no-ai --authorized`.
4. `ghost list` showing saved cases with scope and authorization.
5. `ghost show <id>` case summary with modules and graph size.
6. `ghost export <id>` writing a portable JSON case file.
7. JSON provenance block from `demo-report.json`.

## Talk track

Ghost v2 is prioritizing trust before breadth. The demo should say:

> After import, the investigation is a SQLite case with scope, authorization, and findings. The JSON report adds provenance. SQLite is the local default. Other engines stay behind the storage adapter boundary.

Avoid demoing a random person. Use your own public handle or another explicitly authorized test target.

Redacted sample JSON/Markdown (fake `demo_user` / `alex.rivera.demo@example.com` only) lives in [`examples/`](../examples/). Pull request #24 adds [`docs/screenshots/demo.gif`](screenshots/demo.gif) from `import` / `list` / `show` / `export` on that sample.
