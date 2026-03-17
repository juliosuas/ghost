"""Tests for Ghost investigation engine and backend."""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ghost.core.investigator import (
    GhostInvestigator,
    Investigation,
    _detect_input_type,
    INPUT_TYPE_MODULES,
)
from ghost.backend.db import init_db, save_investigation, get_investigation, list_investigations, get_graph_data, delete_investigation, DB_PATH


# ── Input detection ─────────────────────────────────────────────────

class TestInputDetection:
    def test_email(self):
        assert _detect_input_type("user@example.com") == "email"

    def test_phone_plus(self):
        assert _detect_input_type("+15551234567") == "phone"

    def test_phone_digits(self):
        assert _detect_input_type("555-123-4567") == "phone"

    def test_domain(self):
        assert _detect_input_type("example.com") == "domain"

    def test_domain_subdomain(self):
        assert _detect_input_type("sub.example.co.uk") == "domain"

    def test_name(self):
        assert _detect_input_type("John Doe") == "name"

    def test_username(self):
        assert _detect_input_type("johndoe") == "username"


# ── Investigation model ─────────────────────────────────────────────

class TestInvestigationModel:
    def test_create(self):
        inv = Investigation("johndoe", "username")
        assert inv.target == "johndoe"
        assert inv.input_type == "username"
        assert inv.status == "pending"
        assert inv.risk_score == 0.0
        assert isinstance(inv.id, str) and len(inv.id) == 36

    def test_to_dict(self):
        inv = Investigation("test@example.com", "email")
        d = inv.to_dict()
        assert d["target"] == "test@example.com"
        assert d["input_type"] == "email"
        assert "id" in d
        assert "started_at" in d
        assert d["status"] == "pending"

    def test_to_dict_serializable(self):
        inv = Investigation("target", "username")
        inv.findings = {"username": {"profiles": [{"platform": "GitHub", "url": "https://github.com/target"}]}}
        d = inv.to_dict()
        # Should be JSON-serializable
        json.dumps(d)


# ── Module routing ──────────────────────────────────────────────────

class TestModuleRouting:
    def test_username_modules(self):
        assert "username" in INPUT_TYPE_MODULES["username"]
        assert "social" in INPUT_TYPE_MODULES["username"]

    def test_email_modules(self):
        assert "email" in INPUT_TYPE_MODULES["email"]
        assert "username" in INPUT_TYPE_MODULES["email"]

    def test_phone_modules(self):
        assert "phone" in INPUT_TYPE_MODULES["phone"]

    def test_domain_modules(self):
        assert "domain" in INPUT_TYPE_MODULES["domain"]
        assert "geolocation" in INPUT_TYPE_MODULES["domain"]


# ── Database layer ──────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _setup_test_db(tmp_path, monkeypatch):
    """Use a temporary database for each test."""
    test_db = tmp_path / "test_ghost.db"
    monkeypatch.setattr("ghost.backend.db.DB_PATH", test_db)
    init_db()


class TestDatabase:
    def test_save_and_retrieve(self):
        inv = Investigation("johndoe", "username")
        inv.status = "completed"
        inv.risk_score = 0.65
        inv.summary = "Test summary"
        inv.findings = {
            "username": {
                "username": "johndoe",
                "profiles": [
                    {"platform": "GitHub", "url": "https://github.com/johndoe", "status": "found"},
                    {"platform": "Twitter", "url": "https://x.com/johndoe", "status": "found"},
                ],
                "found_count": 2,
            }
        }
        save_investigation(inv.to_dict())

        loaded = get_investigation(inv.id)
        assert loaded is not None
        assert loaded["target"] == "johndoe"
        assert loaded["status"] == "completed"
        assert loaded["risk_score"] == 0.65
        assert "username" in loaded["findings"]
        assert loaded["findings"]["username"]["found_count"] == 2

    def test_list_investigations(self):
        for i in range(3):
            inv = Investigation(f"target{i}", "username")
            save_investigation(inv.to_dict())
        results = list_investigations()
        assert len(results) == 3

    def test_get_nonexistent(self):
        assert get_investigation("nonexistent-id") is None

    def test_delete(self):
        inv = Investigation("todelete", "username")
        save_investigation(inv.to_dict())
        assert delete_investigation(inv.id) is True
        assert get_investigation(inv.id) is None

    def test_delete_nonexistent(self):
        assert delete_investigation("nope") is False

    def test_graph_data(self):
        inv = Investigation("graphtest", "username")
        inv.findings = {
            "username": {
                "profiles": [
                    {"platform": "GitHub", "url": "https://github.com/graphtest", "status": "found"},
                ]
            }
        }
        save_investigation(inv.to_dict())
        graph = get_graph_data(inv.id)
        assert graph is not None
        assert "nodes" in graph
        assert "links" in graph
        # At least the target node and one profile
        assert len(graph["nodes"]) >= 1

    def test_graph_nonexistent(self):
        assert get_graph_data("nope") is None

    def test_entities_stored(self):
        inv = Investigation("entitytest", "email")
        inv.findings = {
            "email": {
                "email": "test@example.com",
                "breaches": {
                    "breaches": [
                        {"name": "TestBreach", "date": "2023-01-01"},
                    ]
                },
            }
        }
        inv.correlations = {
            "identities": [
                {"type": "email", "value": "test@example.com", "confidence": 0.9}
            ],
            "locations": [
                {"value": "New York", "source": "email"}
            ],
        }
        save_investigation(inv.to_dict())

        loaded = get_investigation(inv.id)
        assert len(loaded["entities"]) > 0
        types = {e["entity_type"] for e in loaded["entities"]}
        assert "target" in types


# ── GhostInvestigator (mocked modules) ─────────────────────────────

class TestGhostInvestigator:
    @patch("ghost.core.investigator.UsernameModule")
    @patch("ghost.core.investigator.EmailModule")
    @patch("ghost.core.investigator.PhoneModule")
    @patch("ghost.core.investigator.SocialModule")
    @patch("ghost.core.investigator.DomainModule")
    @patch("ghost.core.investigator.ImageModule")
    @patch("ghost.core.investigator.DarkWebModule")
    @patch("ghost.core.investigator.GeolocationModule")
    @patch("ghost.core.investigator.Correlator")
    @patch("ghost.core.investigator.AIAnalyzer")
    @patch("ghost.core.investigator.Summarizer")
    def test_investigate_username(
        self, MockSummarizer, MockAnalyzer, MockCorrelator,
        MockGeo, MockDarkweb, MockImage, MockDomain,
        MockSocial, MockPhone, MockEmail, MockUsername,
    ):
        # Set up mocks
        mock_username = MagicMock()
        mock_username.run = AsyncMock(return_value={
            "username": "johndoe",
            "profiles": [{"platform": "GitHub", "url": "https://github.com/johndoe", "status": "found"}],
            "found_count": 1,
        })
        MockUsername.return_value = mock_username

        mock_social = MagicMock()
        mock_social.run = AsyncMock(return_value={"profiles": [], "total_found": 0})
        MockSocial.return_value = mock_social

        mock_darkweb = MagicMock()
        mock_darkweb.run = AsyncMock(return_value={"results": []})
        MockDarkweb.return_value = mock_darkweb

        # Other modules (not called for username type)
        for Mock in (MockEmail, MockPhone, MockDomain, MockImage, MockGeo):
            m = MagicMock()
            m.run = AsyncMock(return_value={})
            Mock.return_value = m

        mock_correlator = MagicMock()
        mock_correlator.correlate = AsyncMock(return_value={
            "identities": [], "connections": [], "timeline": [], "locations": [],
        })
        MockCorrelator.return_value = mock_correlator

        mock_analyzer = MagicMock()
        mock_analyzer.analyze = AsyncMock(return_value={
            "risk_score": 0.3,
            "risk_assessment": {"risk_level": "low"},
        })
        MockAnalyzer.return_value = mock_analyzer

        mock_summarizer = MagicMock()
        mock_summarizer.summarize = AsyncMock(return_value="Test investigation summary.")
        MockSummarizer.return_value = mock_summarizer

        investigator = GhostInvestigator()
        result = asyncio.get_event_loop().run_until_complete(
            investigator.investigate_async("johndoe", "username")
        )

        assert result.status == "completed"
        assert result.target == "johndoe"
        assert "username" in result.findings
        assert result.summary == "Test investigation summary."
        mock_username.run.assert_called_once()

    def test_progress_callback(self):
        events = []
        inv = GhostInvestigator.__new__(GhostInvestigator)
        inv._progress_callback = lambda m, s, d: events.append((m, s, d))
        inv._report_progress("test", "start", "testing")
        assert len(events) == 1
        assert events[0] == ("test", "start", "testing")
