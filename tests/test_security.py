"""Infra/security defaults for the local Flask API and config."""

from pathlib import Path

import pytest

from ghost.core.config import (
    Config,
    is_insecure_secret_key,
    validate_api_token,
    validate_flask_runtime,
    validate_secret_key,
)
from ghost.core.investigator import Investigation
from ghost.backend.db import save_investigation
from ghost.backend import server as server_mod

_TEST_API_TOKEN = "test-api-token-not-for-production"


@pytest.fixture(autouse=True)
def _setup_test_db(tmp_path, monkeypatch):
    test_db = tmp_path / "test_ghost.db"
    monkeypatch.setattr("ghost.backend.db.DB_PATH", test_db)
    from ghost.backend.db import init_db

    init_db()
    server_mod.reset_rate_limiter()


@pytest.fixture
def api_client(monkeypatch):
    monkeypatch.setattr("ghost.core.config.config.api_token", _TEST_API_TOKEN)
    monkeypatch.setattr(server_mod.config, "api_token", _TEST_API_TOKEN)
    return server_mod.app.test_client()


class TestHostAndSecretDefaults:
    def test_host_defaults_to_loopback(self, monkeypatch):
        monkeypatch.delenv("GHOST_HOST", raising=False)
        cfg = Config()
        assert cfg.host == "127.0.0.1"

    def test_secret_key_does_not_soft_default_to_dev_key(self, monkeypatch):
        monkeypatch.delenv("GHOST_SECRET_KEY", raising=False)
        cfg = Config()
        assert cfg.secret_key == ""
        assert cfg.secret_key != "ghost-dev-key"

    def test_insecure_secret_key_detection(self):
        assert is_insecure_secret_key(None) is True
        assert is_insecure_secret_key("") is True
        assert is_insecure_secret_key("   ") is True
        assert is_insecure_secret_key("ghost-dev-key") is True
        assert is_insecure_secret_key("GHOST-DEV-KEY") is True
        assert is_insecure_secret_key("change-this-to-a-random-string") is True
        assert is_insecure_secret_key("a-long-random-secret") is False

    def test_insecure_secret_rejected_outside_debug(self):
        with pytest.raises(ValueError, match="GHOST_SECRET_KEY"):
            validate_secret_key("ghost-dev-key", debug=False)
        with pytest.raises(ValueError, match="GHOST_SECRET_KEY"):
            validate_secret_key("", debug=False)

    def test_insecure_secret_allowed_in_debug(self):
        validate_secret_key("ghost-dev-key", debug=True)
        validate_secret_key("", debug=True)

    def test_flask_runtime_requires_api_token(self):
        cfg = Config()
        cfg.debug = True
        cfg.secret_key = ""
        cfg.api_token = ""
        with pytest.raises(ValueError, match="GHOST_API_TOKEN"):
            validate_flask_runtime(cfg)

    def test_flask_runtime_rejects_insecure_secret_when_not_debug(self):
        cfg = Config()
        cfg.debug = False
        cfg.secret_key = "ghost-dev-key"
        cfg.api_token = "ok-token"
        with pytest.raises(ValueError, match="GHOST_SECRET_KEY"):
            validate_flask_runtime(cfg)

    def test_flask_runtime_accepts_non_debug_with_real_secrets(self):
        cfg = Config()
        cfg.debug = False
        cfg.secret_key = "not-a-placeholder-secret"
        cfg.api_token = "ok-token"
        validate_flask_runtime(cfg)
        validate_api_token("ok-token")


class TestApiTokenAndCors:
    def test_health_is_public(self, api_client):
        response = api_client.get("/api/health")
        assert response.status_code == 200
        assert response.get_json()["status"] == "ok"

    def test_list_investigations_unauthorized_without_token(self, api_client, monkeypatch):
        monkeypatch.setattr(server_mod.config, "api_token", _TEST_API_TOKEN)
        response = api_client.get("/api/investigations")
        assert response.status_code == 401
        assert response.get_json()["error"] == "unauthorized"

    def test_get_investigation_unauthorized_without_token(self, api_client):
        inv = Investigation("johndoe", "username")
        save_investigation(inv.to_dict())
        response = api_client.get(f"/api/investigation/{inv.id}")
        assert response.status_code == 401

    def test_investigate_unauthorized_without_token(self, api_client):
        response = api_client.post(
            "/api/investigate",
            json={"target": "johndoe", "input_type": "username", "authorized_use": True},
        )
        assert response.status_code == 401

    def test_wrong_token_is_unauthorized(self, api_client):
        response = api_client.get(
            "/api/investigations",
            headers={"X-Ghost-Token": "wrong-token"},
        )
        assert response.status_code == 401

    def test_x_ghost_token_allows_read(self, api_client):
        response = api_client.get(
            "/api/investigations",
            headers={"X-Ghost-Token": _TEST_API_TOKEN},
        )
        assert response.status_code == 200
        assert response.get_json() == []

    def test_bearer_token_allows_read(self, api_client):
        response = api_client.get(
            "/api/investigations",
            headers={"Authorization": f"Bearer {_TEST_API_TOKEN}"},
        )
        assert response.status_code == 200

    def test_investigation_pii_requires_token(self, api_client):
        inv = Investigation("secret-target", "email", scope="self-audit", authorized_use=True)
        save_investigation(inv.to_dict())

        denied = api_client.get(f"/api/investigation/{inv.id}")
        assert denied.status_code == 401

        allowed = api_client.get(
            f"/api/investigation/{inv.id}",
            headers={"X-Ghost-Token": _TEST_API_TOKEN},
        )
        assert allowed.status_code == 200
        assert allowed.get_json()["target"] == "secret-target"

    def test_graph_requires_token(self, api_client):
        inv = Investigation("graphtarget", "username")
        save_investigation(inv.to_dict())
        denied = api_client.get(f"/api/investigation/{inv.id}/graph")
        assert denied.status_code == 401

    def test_cors_is_not_wildcard(self, api_client):
        response = api_client.get(
            "/api/investigations",
            headers={
                "X-Ghost-Token": _TEST_API_TOKEN,
                "Origin": "https://evil.example",
            },
        )
        allow = response.headers.get("Access-Control-Allow-Origin")
        assert allow != "*"
        assert allow != "https://evil.example"

    def test_cors_allows_localhost(self, api_client):
        response = api_client.get(
            "/api/investigations",
            headers={
                "X-Ghost-Token": _TEST_API_TOKEN,
                "Origin": "http://127.0.0.1:5000",
            },
        )
        assert response.headers.get("Access-Control-Allow-Origin") == "http://127.0.0.1:5000"

    def test_missing_api_token_config_fails_closed(self, monkeypatch):
        monkeypatch.setattr(server_mod.config, "api_token", "")
        client = server_mod.app.test_client()
        response = client.get(
            "/api/investigations",
            headers={"X-Ghost-Token": "anything"},
        )
        assert response.status_code == 401


class TestApiRateLimit:
    def test_rate_limit_config_is_enforced(self, monkeypatch):
        monkeypatch.setattr(server_mod.config, "api_token", _TEST_API_TOKEN)
        monkeypatch.setattr(server_mod.config, "rate_limit_requests", 1)
        monkeypatch.setattr(server_mod.config, "rate_limit_period", 60)
        server_mod.reset_rate_limiter()
        client = server_mod.app.test_client()
        headers = {"X-Ghost-Token": _TEST_API_TOKEN}

        first = client.get("/api/investigations", headers=headers)
        second = client.get("/api/investigations", headers=headers)

        assert first.status_code == 200
        assert second.status_code == 429
        assert second.get_json()["error"] == "rate limit exceeded"

    def test_health_is_not_rate_limited(self, monkeypatch):
        monkeypatch.setattr(server_mod.config, "rate_limit_requests", 1)
        monkeypatch.setattr(server_mod.config, "rate_limit_period", 60)
        server_mod.reset_rate_limiter()
        client = server_mod.app.test_client()

        assert client.get("/api/health").status_code == 200
        assert client.get("/api/health").status_code == 200


class TestEnvAndComposeDefaults:
    def test_env_example_uses_locked_names_and_loopback_host(self):
        text = (Path(__file__).resolve().parents[1] / ".env.example").read_text(encoding="utf-8")
        assert "GHOST_SECRET_KEY=" in text
        assert "GHOST_HOST=127.0.0.1" in text
        assert "GHOST_API_TOKEN=" in text
        assert "GHOST_HOST=0.0.0.0" not in text

    def test_compose_publishes_loopback_not_all_interfaces(self):
        text = (Path(__file__).resolve().parents[1] / "docker-compose.yml").read_text(encoding="utf-8")
        assert "127.0.0.1:${GHOST_PORT:-5000}:5000" in text
        assert '"0.0.0.0:' not in text
        assert "urllib.request" in text
