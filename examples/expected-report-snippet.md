# Expected JSON report snippet

`ghost investigate … --format json` writes an `Investigation.to_dict()` payload plus a `provenance` object from `ghost.core.report_generator`. The excerpt below matches that contract for the synthetic username sample (fake handle only).

```json
{
  "target": "demo_user",
  "input_type": "username",
  "scope": "authorized self-audit demo",
  "authorized_use": true,
  "status": "completed",
  "summary": "Investigation of username target: demo_user\n\nData collected from 1 intelligence modules. Found 3 associated online profiles.\n\nOverall risk assessment: LOW (score: 10.0%)",
  "risk_score": 0.1,
  "findings": {
    "username": {
      "username": "demo_user",
      "platforms_checked": 70,
      "found_count": 3
    }
  },
  "provenance": {
    "target": "demo_user",
    "input_type": "username",
    "scope": "authorized self-audit demo",
    "authorized_use": true,
    "modules_run": ["username"],
    "module_count": 1,
    "source_urls": [
      "https://github.com/demo_user",
      "https://gitlab.com/demo_user",
      "https://www.reddit.com/user/demo_user"
    ],
    "source_url_count": 3,
    "module_errors": {},
    "global_errors": []
  }
}
```

Inspect provenance on a live demo with:

```bash
python3 -c "import json; print(json.dumps(json.load(open('demo-report.json'))['provenance'], indent=2))"
```

Or `jq '.provenance'` if `jq` is installed. See [docs/self-audit-demo.md](../docs/self-audit-demo.md).
