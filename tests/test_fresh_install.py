"""First-run CLI behavior against a database file that does not exist yet."""

import json
from pathlib import Path

from click.testing import CliRunner

from ghost.ui.cli import cli

SAMPLE = Path(__file__).resolve().parents[1] / "examples" / "sample-username-case.json"


def _fresh_db(tmp_path, monkeypatch):
    db_path = tmp_path / "fresh" / "ghost.db"
    monkeypatch.setattr("ghost.backend.db.DB_PATH", db_path)
    assert not db_path.exists()
    return db_path


def test_list_on_fresh_install_returns_empty(tmp_path, monkeypatch):
    db_path = _fresh_db(tmp_path, monkeypatch)
    result = CliRunner().invoke(cli, ["list", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == []
    assert db_path.exists()


def test_import_then_show_on_fresh_install(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    runner = CliRunner()
    imported = runner.invoke(cli, ["import", str(SAMPLE)])
    assert imported.exit_code == 0, imported.output
    shown = runner.invoke(cli, ["show", "a1b2c3d4"])
    assert shown.exit_code == 0, shown.output
    assert "demo_user" in shown.output
