# Sample investigations

Synthetic, authorized-looking artifacts so newcomers can see Ghost's case-file and report shape **without running a live hunt against a real person**.

| File | What it is |
|---|---|
| [`sample-username-case.json`](sample-username-case.json) | Portable case file (`ghost import` compatible). Fake handle only. |
| [`sample-email-investigation.md`](sample-email-investigation.md) | Markdown write-up of a fake email self-audit. |
| [`expected-report-snippet.md`](expected-report-snippet.md) | Short JSON report excerpt (`summary` + `provenance`) matching `ghost investigate --format json`. |

All names, emails, and profile URLs are invented (`demo_user`, `alex.rivera.demo@example.com`). Sample profile links use non-resolving `*.example.com` placeholders, not live GitHub/GitLab/Reddit hits. Do not treat them as real OSINT results.

## Import the username case

```bash
python3 -m pip install -e .
python3 -m ghost import examples/sample-username-case.json
python3 -m ghost show a1b2c3d4
python3 -m ghost list
```

Re-import with `--replace` if that ID already exists locally.

## Generate a live report instead

Prefer the [authorized self-audit demo](../docs/self-audit-demo.md) against **your own** public handle. Replace `YOUR_HANDLE` before running (`--authorized` does not make `demo_user` your target):

```bash
python3 -m ghost investigate YOUR_HANDLE \
  --type username \
  --modules username \
  --no-ai \
  --authorized \
  --scope "authorized self-audit demo" \
  --format json \
  --output demo-report.json
```
