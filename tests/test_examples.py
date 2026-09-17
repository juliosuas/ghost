"""Keep example artifacts valid so docs stay honest."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from ghost.backend.db import get_investigation, init_db
from ghost.core.report_generator import ReportGenerator
from ghost.ui.cli import cli

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
SAMPLE_CASE = EXAMPLES / "sample-username-case.json"


@pytest.fixture(autouse=True)
def _setup_test_db(tmp_path, monkeypatch):
    test_db = tmp_path / "test_ghost.db"
    monkeypatch.setattr("ghost.backend.db.DB_PATH", test_db)
    init_db()


def test_sample_username_case_is_importable():
    data = json.loads(SAMPLE_CASE.read_text(encoding="utf-8"))
    required = {"id", "target", "input_type", "status", "started_at"}
    assert required <= set(data)
    assert data["target"] == "demo_user"
    assert data["authorized_use"] is True
    assert "@" not in data["target"]

    result = CliRunner().invoke(cli, ["import", str(SAMPLE_CASE)])
    assert result.exit_code == 0, result.output

    loaded = get_investigation(data["id"])
    assert loaded is not None
    assert loaded["scope"] == "authorized self-audit demo"
    assert loaded["findings"]["username"]["platforms_checked"] == 70
    assert loaded["findings"]["username"]["found_count"] == 3


def test_sample_case_report_provenance(tmp_path):
    data = json.loads(SAMPLE_CASE.read_text(encoding="utf-8"))
    output = tmp_path / "report.json"
    ReportGenerator().generate(data, "json", str(output))

    report = json.loads(output.read_text(encoding="utf-8"))
    provenance = report["provenance"]
    assert provenance["authorized_use"] is True
    assert provenance["scope"] == "authorized self-audit demo"
    assert provenance["modules_run"] == ["username"]
    assert provenance["source_url_count"] == 3
    assert "https://github.com/demo_user" in provenance["source_urls"]
