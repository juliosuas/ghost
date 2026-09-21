"""Tests for ghost doctor exposure gates and JSON/CLI contracts."""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from ghost.core.doctor import has_error, run_doctor_checks, summarize_doctor_checks
from ghost.ui.cli import cli

SECURE_SECRET = "unit-test-secret-not-a-default"
SECURE_TOKEN = "unit-test-api-token"


def _check(checks, name: str):
    return next(item for item in checks if item.name == name)


@pytest.fixture
def secure_env(monkeypatch):
    """Loopback-ready server env: secret + token set, host on 127.0.0.1."""
    monkeypatch.setenv("GHOST_SECRET_KEY", SECURE_SECRET)
    monkeypatch.setenv("GHOST_HOST", "127.0.0.1")
    monkeypatch.setenv("GHOST_API_TOKEN", SECURE_TOKEN)


@pytest.fixture
def cli_only_env(monkeypatch):
    """CLI-only: secret + token set so doctor can pass; host unset is allowed."""
    monkeypatch.setenv("GHOST_SECRET_KEY", SECURE_SECRET)
    monkeypatch.setenv("GHOST_API_TOKEN", SECURE_TOKEN)
    monkeypatch.delenv("GHOST_HOST", raising=False)


@pytest.fixture
def insecure_default_env(monkeypatch):
    """Fresh clone: no secret, no token, host unset."""
    monkeypatch.delenv("GHOST_SECRET_KEY", raising=False)
    monkeypatch.delenv("GHOST_HOST", raising=False)
    monkeypatch.delenv("GHOST_API_TOKEN", raising=False)


class TestDoctorExposureGates:
    def test_fresh_clone_fails_closed_on_missing_secret_and_token(self, insecure_default_env):
        checks = run_doctor_checks()
        summary = summarize_doctor_checks(checks)

        assert _check(checks, "GHOST_SECRET_KEY").ok is False
        assert _check(checks, "GHOST_SECRET_KEY").severity == "error"
        assert "missing" in _check(checks, "GHOST_SECRET_KEY").detail
        assert _check(checks, "GHOST_API_TOKEN").ok is False
        assert "empty" in _check(checks, "GHOST_API_TOKEN").detail
        # Unset host is OK for CLI-only; Flask is not started by investigate.
        assert _check(checks, "GHOST_HOST").ok is True
        assert "unset" in _check(checks, "GHOST_HOST").detail
        assert has_error(checks) is True
        assert summary["ok"] is False
        assert summary["error_count"] >= 2

    def test_insecure_secret_default_fails(self, monkeypatch, cli_only_env):
        monkeypatch.setenv("GHOST_SECRET_KEY", "ghost-dev-key")
        checks = run_doctor_checks()
        secret = _check(checks, "GHOST_SECRET_KEY")
        assert secret.ok is False
        assert secret.severity == "error"
        assert "insecure" in secret.detail
        assert has_error(checks) is True
        assert summarize_doctor_checks(checks)["ok"] is False

    def test_example_placeholder_secret_fails(self, monkeypatch, cli_only_env):
        monkeypatch.setenv("GHOST_SECRET_KEY", "change-this-to-a-random-string")
        checks = run_doctor_checks()
        assert _check(checks, "GHOST_SECRET_KEY").ok is False

    def test_blank_secret_fails(self, monkeypatch, cli_only_env):
        monkeypatch.setenv("GHOST_SECRET_KEY", "   ")
        checks = run_doctor_checks()
        assert _check(checks, "GHOST_SECRET_KEY").ok is False

    def test_public_host_fails(self, monkeypatch, cli_only_env):
        monkeypatch.setenv("GHOST_HOST", "0.0.0.0")
        checks = run_doctor_checks()
        host = _check(checks, "GHOST_HOST")
        assert host.ok is False
        assert host.severity == "error"
        assert "0.0.0.0" in host.detail
        assert has_error(checks) is True

    @pytest.mark.parametrize("host", ["8.8.8.8", "example.com", "::"])
    def test_non_loopback_host_fails(self, monkeypatch, cli_only_env, host):
        monkeypatch.setenv("GHOST_HOST", host)
        checks = run_doctor_checks()
        assert _check(checks, "GHOST_HOST").ok is False

    @pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "LOCALHOST", "::1"])
    def test_loopback_host_passes(self, monkeypatch, cli_only_env, host):
        monkeypatch.setenv("GHOST_HOST", host)
        checks = run_doctor_checks()
        assert _check(checks, "GHOST_HOST").ok is True
        assert has_error(checks) is False

    def test_unset_host_passes_when_secret_and_token_set(self, cli_only_env):
        checks = run_doctor_checks()
        assert _check(checks, "GHOST_HOST").ok is True
        assert has_error(checks) is False
        assert summarize_doctor_checks(checks)["ok"] is True

    def test_empty_api_token_fails(self, monkeypatch, secure_env):
        monkeypatch.setenv("GHOST_API_TOKEN", "")
        checks = run_doctor_checks()
        token = _check(checks, "GHOST_API_TOKEN")
        assert token.ok is False
        assert token.severity == "error"
        assert has_error(checks) is True

    def test_secure_env_passes(self, secure_env):
        checks = run_doctor_checks()
        summary = summarize_doctor_checks(checks)
        assert _check(checks, "GHOST_SECRET_KEY").ok is True
        assert _check(checks, "GHOST_HOST").ok is True
        assert _check(checks, "GHOST_API_TOKEN").ok is True
        assert has_error(checks) is False
        assert summary["ok"] is True
        assert summary["error_count"] == 0
        names = {item["name"] for item in summary["checks"]}
        assert {"GHOST_SECRET_KEY", "GHOST_HOST", "GHOST_API_TOKEN"} <= names


class TestDoctorCli:
    def test_json_exits_nonzero_on_insecure_defaults(self, insecure_default_env):
        result = CliRunner().invoke(cli, ["doctor", "--json"])
        assert result.exit_code == 1
        payload = json.loads(result.output)
        assert payload["ok"] is False
        assert payload["error_count"] >= 2
        by_name = {item["name"]: item for item in payload["checks"]}
        assert by_name["GHOST_SECRET_KEY"]["ok"] is False
        assert by_name["GHOST_API_TOKEN"]["ok"] is False
        assert by_name["GHOST_HOST"]["ok"] is True

    def test_json_exits_zero_on_secure_env(self, secure_env):
        result = CliRunner().invoke(cli, ["doctor", "--json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["ok"] is True
        assert payload["error_count"] == 0

    def test_human_output_exits_nonzero_on_insecure_defaults(self, insecure_default_env):
        result = CliRunner().invoke(cli, ["doctor"])
        assert result.exit_code == 1
        assert "FAIL" in result.output
        assert "GHOST_SECRET_KEY" in result.output
        assert "GHOST_API_TOKEN" in result.output

    def test_help_documents_exposure_gates(self):
        result = CliRunner().invoke(cli, ["doctor", "--help"])
        assert result.exit_code == 0
        assert "GHOST_SECRET_KEY" in result.output
        assert "GHOST_HOST" in result.output
        assert "GHOST_API_TOKEN" in result.output
        assert "investigate" in result.output

    def test_investigate_help_does_not_require_secure_env(self, insecure_default_env):
        """CLI-only self-audit must remain usable when doctor would fail closed."""
        result = CliRunner().invoke(cli, ["investigate", "--help"])
        assert result.exit_code == 0
        assert "--authorized" in result.output
        assert "--no-ai" in result.output
