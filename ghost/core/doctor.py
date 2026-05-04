"""Environment checks for Ghost CLI/API deployments."""

from __future__ import annotations

import importlib.util
import shutil
from dataclasses import dataclass

from ghost.backend.db import DB_PATH, get_connection, init_db
from ghost.core.config import Config, config


@dataclass(frozen=True)
class DoctorCheck:
    """A single local readiness check."""

    name: str
    ok: bool
    detail: str
    severity: str = "warn"


def run_doctor_checks(config_override: Config | None = None) -> list[DoctorCheck]:
    """Return local readiness checks without printing or exiting."""
    cfg = config_override or config
    checks: list[DoctorCheck] = []

    try:
        init_db()
        with get_connection() as conn:
            conn.execute("SELECT 1").fetchone()
        checks.append(DoctorCheck("database", True, str(DB_PATH), "error"))
    except Exception as exc:
        checks.append(DoctorCheck("database", False, str(exc), "error"))

    checks.append(DoctorCheck(
        "OpenAI key",
        cfg.has_api_key("openai_api_key"),
        "set" if cfg.has_api_key("openai_api_key") else "missing; fallback summaries still work",
    ))

    for package, label in [
        ("aiohttp", "HTTP collection"),
        ("rich", "CLI UI"),
        ("flask", "REST API"),
        ("phonenumbers", "Phone module"),
        ("dns", "Domain DNS module"),
    ]:
        checks.append(DoctorCheck(label, importlib.util.find_spec(package) is not None, package, "error"))

    for binary, label in [("sherlock", "Sherlock optional username coverage")]:
        found = shutil.which(binary)
        checks.append(DoctorCheck(label, bool(found), found or "not installed; built-in platform checks still run"))

    checks.append(DoctorCheck("enabled modules", bool(cfg.enabled_modules), ", ".join(cfg.enabled_modules), "error"))
    return checks


def has_error(checks: list[DoctorCheck]) -> bool:
    """Whether any hard-error doctor check failed."""
    return any(not check.ok and check.severity == "error" for check in checks)
