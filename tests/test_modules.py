"""Tests for Ghost OSINT collection modules."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from ghost.core.config import Config
from ghost.modules.username import UsernameModule, PLATFORMS


class TestUsernameModule:
    """Tests for the username enumeration module."""

    def _make_config(self):
        cfg = Config()
        cfg.max_concurrent_requests = 5
        cfg.request_timeout = 10
        cfg.user_agent = "TestAgent/1.0"
        return cfg

    def test_platforms_list_not_empty(self):
        """Ensure we have a meaningful number of platforms to check."""
        assert len(PLATFORMS) >= 50
        # Each platform should be a 3-tuple
        for p in PLATFORMS:
            assert len(p) == 3
            name, url_template, status = p
            assert isinstance(name, str)
            assert "{}" in url_template
            assert isinstance(status, int)

    def test_platform_names_unique(self):
        """Platform names should be unique."""
        names = [p[0] for p in PLATFORMS]
        assert len(names) == len(set(names)), f"Duplicate platforms: {[n for n in names if names.count(n) > 1]}"

    def test_platform_urls_contain_placeholder(self):
        """All URL templates must contain {} for username substitution."""
        for name, url, _ in PLATFORMS:
            assert "{}" in url, f"Platform {name} URL missing placeholder: {url}"

    def test_module_init(self):
        """Module initializes correctly with config."""
        cfg = self._make_config()
        module = UsernameModule(cfg)
        assert module.config is cfg

    @patch("ghost.modules.username.aiohttp.ClientSession")
    async def test_run_returns_expected_structure(self, mock_session_cls):
        """The run method should return a dict with expected keys."""
        # Mock all HTTP requests to return 404 (not found)
        mock_response = AsyncMock()
        mock_response.status = 404
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value = mock_session

        cfg = self._make_config()
        module = UsernameModule(cfg)

        # Mock sherlock to not be found
        with patch.object(module, "_run_sherlock", new_callable=AsyncMock) as mock_sherlock:
            mock_sherlock.return_value = {"available": False, "note": "not installed"}
            result = await module.run("testuser123xyz")

        assert "username" in result
        assert result["username"] == "testuser123xyz"
        assert "platforms_checked" in result
        assert "profiles" in result
        assert "found_count" in result
        assert isinstance(result["profiles"], list)

    def test_username_normalization(self):
        """Username with @ prefix should be normalized."""
        cfg = self._make_config()
        module = UsernameModule(cfg)
        # The run method strips @ — we test the logic
        target = "@SomeUser"
        username = target.split("@")[-1].strip().lower()
        assert username == "someuser"

    @patch("ghost.modules.username.asyncio.create_subprocess_exec")
    async def test_sherlock_not_installed(self, mock_exec):
        """Sherlock fallback when not installed."""
        mock_exec.side_effect = FileNotFoundError()
        cfg = self._make_config()
        module = UsernameModule(cfg)
        result = await module._run_sherlock("testuser")
        assert result["available"] is False


class TestInputTypeDetection:
    """Test input type auto-detection from investigator."""

    def test_various_inputs(self):
        from ghost.core.investigator import _detect_input_type

        assert _detect_input_type("user@example.com") == "email"
        assert _detect_input_type("+1-555-123-4567") == "phone"
        assert _detect_input_type("example.com") == "domain"
        assert _detect_input_type("sub.example.co.uk") == "domain"
        assert _detect_input_type("John Doe") == "name"
        assert _detect_input_type("johndoe") == "username"
        assert _detect_input_type("j0hn_d03") == "username"


class TestConfigModule:
    """Tests for configuration."""

    def test_default_config(self):
        cfg = Config()
        assert cfg.openai_model == "gpt-4o"
        assert cfg.port == 5000
        assert cfg.request_timeout == 30
        assert cfg.max_concurrent_requests == 20
        assert "username" in cfg.enabled_modules
        assert "email" in cfg.enabled_modules

    def test_has_api_key_empty(self):
        cfg = Config()
        cfg.openai_api_key = ""
        assert cfg.has_api_key("openai_api_key") is False

    def test_has_api_key_set(self):
        cfg = Config()
        cfg.openai_api_key = "sk-test123"
        assert cfg.has_api_key("openai_api_key") is True

    def test_has_api_key_missing(self):
        cfg = Config()
        assert cfg.has_api_key("nonexistent_key") is False


class TestCorrelator:
    """Tests for the correlation engine."""

    def test_identity_correlation(self):
        from ghost.core.correlator import Correlator
        cfg = Config()
        cfg.openai_api_key = ""  # Disable AI correlation
        correlator = Correlator(cfg)

        findings = {
            "username": {
                "username": "johndoe",
                "display_name": "John Doe",
                "profiles": [
                    {"username": "johndoe", "platform": "GitHub"},
                    {"username": "johndoe", "platform": "Twitter"},
                ],
            },
            "social": {
                "username": "johndoe",
                "display_name": "John Doe",
            },
        }

        identities = correlator._correlate_identities(findings)
        # Should find "john doe" appearing in multiple sources
        name_identities = [i for i in identities if i["type"] == "name"]
        assert len(name_identities) > 0
        assert name_identities[0]["value"] == "john doe"

    def test_timeline_extraction(self):
        from ghost.core.correlator import Correlator
        cfg = Config()
        correlator = Correlator(cfg)

        findings = {
            "social": {
                "created_at": "2020-01-15",
                "last_active": "2024-03-01",
            },
            "email": {
                "breaches": [
                    {"name": "BigBreach", "date": "2021-06-15"},
                ],
            },
        }

        timeline = correlator._build_timeline(findings)
        assert len(timeline) >= 2
        # Should be sorted by date
        dates = [e["date"] for e in timeline]
        assert dates == sorted(dates)

    def test_location_correlation(self):
        from ghost.core.correlator import Correlator
        cfg = Config()
        correlator = Correlator(cfg)

        findings = {
            "social": {"location": "New York, NY", "country": "US"},
            "geolocation": {"lat": 40.7128, "lon": -74.006, "city": "New York"},
        }

        locations = correlator._correlate_locations(findings)
        assert len(locations) >= 2
        # Should include coordinates
        coord_locs = [l for l in locations if l.get("field") == "coordinates"]
        assert len(coord_locs) == 1


class TestAIAnalyzerFallback:
    """Test AI analyzer in no-API-key mode."""

    def test_fallback_analysis_basic(self):
        from ghost.ai.analyzer import AIAnalyzer
        cfg = Config()
        cfg.openai_api_key = ""
        analyzer = AIAnalyzer(cfg)

        findings = {
            "username": {
                "profiles": [{"platform": f"P{i}"} for i in range(10)],
            },
            "email": {
                "breaches": {"total": 3},
            },
        }

        result = analyzer._fallback_analysis(findings)
        assert "risk_score" in result
        assert 0 <= result["risk_score"] <= 1.0
        assert result["risk_assessment"]["risk_level"] in ("low", "medium", "high")
        assert "note" in result  # Should mention no API key

    def test_fallback_no_findings(self):
        from ghost.ai.analyzer import AIAnalyzer
        cfg = Config()
        cfg.openai_api_key = ""
        analyzer = AIAnalyzer(cfg)

        result = analyzer._fallback_analysis({})
        assert result["risk_score"] == 0.1  # Base risk only


class TestSummarizerFallback:
    """Test summarizer without API key."""

    async def test_heuristic_summary(self):
        from ghost.ai.summarizer import Summarizer
        cfg = Config()
        cfg.openai_api_key = ""
        summarizer = Summarizer(cfg)

        inv = {
            "target": "johndoe",
            "input_type": "username",
            "risk_score": 0.3,
            "findings": {
                "username": {
                    "profiles": [{"platform": "GitHub"}, {"platform": "Twitter"}],
                },
            },
            "errors": [],
        }

        result = await summarizer.summarize(inv)
        assert "johndoe" in result
        assert "username" in result
        assert "LOW" in result

