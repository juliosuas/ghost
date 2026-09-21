# Sample email investigation (synthetic)

This is a **redacted teaching example**, not a live Ghost run. The address is invented.

- **Target:** `alex.rivera.demo@example.com`
- **Type:** `email`
- **Scope:** authorized self-audit demo
- **Authorized:** yes
- **AI:** disabled (`--no-ai`)
- **Modules that would run for `email`:** `email`, `username`. `social` and `darkweb` are experimental and **off by default** (see `INPUT_TYPE_MODULES` in `ghost/core/investigator.py`).

## Command (authorized use only)

```bash
python3 -m ghost investigate alex.rivera.demo@example.com \
  --type email \
  --modules email \
  --no-ai \
  --authorized \
  --scope "authorized self-audit demo" \
  --format json \
  --output demo-email-report.json
```

Restrict `--modules email` in demos if you do not want Ghost to also run the username collector on a handle derived from the mailbox. Social/darkweb stay off unless you pass `--modules social` or `--modules darkweb`.

## Expected module fields

When the email module completes without errors, `findings.email` looks like:

```json
{
  "email": "alex.rivera.demo@example.com",
  "validation": {
    "valid_format": true,
    "domain": "example.com",
    "has_mx": true,
    "provider": "example",
    "disposable": false
  },
  "breaches": {
    "total": 0,
    "breaches": [],
    "api_available": false
  },
  "accounts": { "accounts": [], "count": 0 },
  "domain": { "domain": "example.com" },
  "gravatar": { "found": false }
}
```

`breaches.api_available` is `false` unless `HIBP_API_KEY` is set. Do not invent Have I Been Pwned hits in public samples.

## Case-file notes

After the run, `ghost list` should show the target, `email` type, `authorized` = yes, and the recorded scope. `ghost show <id-prefix>` prints the heuristic summary and which finding modules were stored.
