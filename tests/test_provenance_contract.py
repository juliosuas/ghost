"""Contract freeze for ReportGenerator._build_provenance keys.

Fails CI if a key is removed or silently added. Does not call HTTP, OpenAI,
or live OSINT modules. Does not change report_generator.py.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from ghost.core.report_generator import ReportGenerator

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_CASE = REPO_ROOT / "examples" / "sample-username-case.json"
EXPECTED_SNIPPET = REPO_ROOT / "examples" / "expected-report-snippet.md"

# Exact keys emitted by ReportGenerator._build_provenance today.
PROVENANCE_CONTRACT_KEYS = frozenset(
    {
        "generated_at",
        "target",
        "input_type",
        "investigation_id",
        "scope",
        "authorized_use",
        "modules_run",
        "module_count",
        "source_urls",
        "source_url_count",
        "module_errors",
        "global_errors",
    }
)


def _sample_case() -> dict:
    return json.loads(SAMPLE_CASE.read_text(encoding="utf-8"))


def _generate_provenance(tmp_path) -> tuple[dict, dict]:
    case = _sample_case()
    output = tmp_path / "provenance-contract.json"
    ReportGenerator().generate(case, "json", str(output))
    report = json.loads(output.read_text(encoding="utf-8"))
    return case, report


class TestProvenanceContract:
    def test_sample_case_provenance_keyset_is_frozen(self, tmp_path):
        _case, report = _generate_provenance(tmp_path)
        provenance = report["provenance"]
        assert set(provenance) == PROVENANCE_CONTRACT_KEYS

    def test_sample_case_self_audit_values(self, tmp_path):
        case, report = _generate_provenance(tmp_path)
        provenance = report["provenance"]

        assert provenance["authorized_use"] is True
        assert provenance["scope"] == "authorized self-audit demo"
        assert provenance["target"] == "demo_user"
        assert provenance["input_type"] == "username"
        assert provenance["investigation_id"] == case["id"]
        assert provenance["modules_run"] == ["username"]
        assert provenance["module_count"] == 1
        assert provenance["source_url_count"] == 3
        assert len(provenance["source_urls"]) == 3
        assert all(".example.com" in url for url in provenance["source_urls"])
        assert provenance["module_errors"] == {}
        assert provenance["global_errors"] == []

    def test_generated_at_is_parseable_iso8601(self, tmp_path):
        _case, report = _generate_provenance(tmp_path)
        generated_at = report["provenance"]["generated_at"]
        parsed = datetime.fromisoformat(generated_at)
        assert parsed.tzinfo is not None

    def test_missing_contract_key_would_fail(self):
        """Guard the freeze itself: the production helper must still emit every key."""
        from ghost.core.report_generator import ReportGenerator as RG

        inv = {
            "id": "00000000-0000-0000-0000-000000000000",
            "target": "demo_user",
            "input_type": "username",
            "scope": "authorized self-audit demo",
            "authorized_use": True,
            "findings": {},
            "errors": [],
        }
        provenance = RG()._build_provenance(inv)
        assert set(provenance) == PROVENANCE_CONTRACT_KEYS

    def test_expected_snippet_keys_are_a_subset_of_the_contract(self):
        """The markdown snippet omits generated_at / investigation_id; live reports must not."""
        text = EXPECTED_SNIPPET.read_text(encoding="utf-8")
        match = re.search(r"```json\n(\{.*?\n\})\n```", text, re.DOTALL)
        assert match, "examples/expected-report-snippet.md must contain a json fence"
        snippet = json.loads(match.group(1))
        snippet_keys = set(snippet["provenance"])
        assert snippet_keys <= PROVENANCE_CONTRACT_KEYS
        assert "generated_at" not in snippet_keys
        assert "investigation_id" not in snippet_keys
