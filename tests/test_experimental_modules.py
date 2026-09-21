"""Experimental social/darkweb collectors are off by default and opt-in."""

from __future__ import annotations

import asyncio
from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

from ghost.core.config import Config
from ghost.core.investigator import (
    EXPERIMENTAL_MODULES,
    INPUT_TYPE_MODULES,
    GhostInvestigator,
)

_MODULE_PATCHES = (
    "ghost.core.investigator.UsernameModule",
    "ghost.core.investigator.EmailModule",
    "ghost.core.investigator.PhoneModule",
    "ghost.core.investigator.SocialModule",
    "ghost.core.investigator.DomainModule",
    "ghost.core.investigator.ImageModule",
    "ghost.core.investigator.DarkWebModule",
    "ghost.core.investigator.GeolocationModule",
    "ghost.core.investigator.Correlator",
    "ghost.core.investigator.AIAnalyzer",
    "ghost.core.investigator.Summarizer",
)


def test_experimental_modules_constant():
    assert EXPERIMENTAL_MODULES == frozenset({"social", "darkweb"})


def test_input_type_defaults_exclude_experimental():
    for input_type, modules in INPUT_TYPE_MODULES.items():
        overlap = EXPERIMENTAL_MODULES & set(modules)
        assert not overlap, f"{input_type} still auto-runs {sorted(overlap)}"


def test_default_enabled_modules_exclude_experimental():
    cfg = Config()
    assert EXPERIMENTAL_MODULES.isdisjoint(cfg.enabled_modules)
    assert "username" in cfg.enabled_modules
    assert "email" in cfg.enabled_modules


def _ready_module(mock_cls, payload):
    instance = MagicMock()
    instance.run = AsyncMock(return_value=payload)
    mock_cls.return_value = instance
    return instance


def _stub_pipeline(stack: ExitStack) -> dict:
    mocks = {name.rsplit(".", 1)[-1]: stack.enter_context(patch(name)) for name in _MODULE_PATCHES}
    username = _ready_module(mocks["UsernameModule"], {"username": "johndoe", "profiles": [], "found_count": 0})
    social = _ready_module(mocks["SocialModule"], {"profiles": [], "total_found": 0})
    darkweb = _ready_module(mocks["DarkWebModule"], {"results": []})
    for key in ("EmailModule", "PhoneModule", "DomainModule", "ImageModule", "GeolocationModule"):
        _ready_module(mocks[key], {})
    mocks["Correlator"].return_value.correlate = AsyncMock(
        return_value={"identities": [], "connections": [], "timeline": [], "locations": []}
    )
    mocks["AIAnalyzer"].return_value.analyze = AsyncMock(return_value={"risk_score": 0.0})
    mocks["Summarizer"].return_value.summarize = AsyncMock(return_value="ok")
    return {"username": username, "social": social, "darkweb": darkweb}


class TestExperimentalOptIn:
    def test_username_default_does_not_run_social_or_darkweb(self):
        with ExitStack() as stack:
            runs = _stub_pipeline(stack)
            result = asyncio.run(GhostInvestigator().investigate_async("johndoe", "username"))

        runs["username"].run.assert_called_once()
        runs["social"].run.assert_not_called()
        runs["darkweb"].run.assert_not_called()
        assert set(result.findings) == {"username"}

    def test_explicit_modules_social_runs_even_when_not_enabled(self):
        with ExitStack() as stack:
            runs = _stub_pipeline(stack)
            cfg = Config()
            cfg.enabled_modules = ["username", "email", "phone", "domain", "image", "geolocation"]
            result = asyncio.run(
                GhostInvestigator(config_override=cfg).investigate_async("johndoe", "username", modules=["social"])
            )

        runs["social"].run.assert_called_once()
        runs["darkweb"].run.assert_not_called()
        runs["username"].run.assert_not_called()
        assert "social" in result.findings
        assert "username" not in result.findings
