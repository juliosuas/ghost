"""Environment checks for Ghost CLI/API deployments."""

from __future__ import annotations

import importlib.util
import os
import shutil
from dataclasses import dataclass

from ghost.backend.db import DB_PATH, get_connection, init_db, resolve_database_path
from ghost.core.config import Config, config

# Known insecure Flask/session defaults. Doctor fails if GHOST_SECRET_KEY is
# missing or equals one of these (including the Config class default).
INSECURE_SECRET_DEFAULTS = frozenset(
    {
        "ghost-dev-key",
        "change-this-to-a-random-string",
    }
)

# Doctor allows only loopback binds when GHOST_HOST is set. Unset is OK for CLI-only.
ALLOWED_BIND_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


@dataclass(frozen=True)
class DoctorCheck:
    """A single local readiness check."""

    name: str
    ok: bool
    detail: str
    severity: str = "warn"


def _read_env(name: str) -> str | None:
    """Return a live environment value, or None if the variable is unset.

    Class-level Config defaults are ignored so doctor can tell "unset GHOST_HOST"
    (CLI-only OK) from an explicit 0.0.0.0 / public bind (fail closed).
    """
    if name in os.environ:
        return os.environ[name]
    return None


def _secret_key_check() -> DoctorCheck:
    raw = _read_env("GHOST_SECRET_KEY")
    if raw is None:
        return DoctorCheck(
            "GHOST_SECRET_KEY",
            False,
            "missing; set a random value before starting Flask "
            "(CLI-only investigate --authorized --no-ai does not need this)",
            "error",
        )
    value = raw.strip()
    if not value or value in INSECURE_SECRET_DEFAULTS:
        return DoctorCheck(
            "GHOST_SECRET_KEY",
            False,
            "insecure default or empty; refuse ghost-dev-key / example placeholders",
            "error",
        )
    return DoctorCheck("GHOST_SECRET_KEY", True, "set", "error")


def _host_check() -> DoctorCheck:
    raw = _read_env("GHOST_HOST")
    if raw is None or not str(raw).strip():
        return DoctorCheck(
            "GHOST_HOST",
            True,
            "unset (CLI-only OK; set 127.0.0.1 or localhost before starting Flask; the code default is still 0.0.0.0)",
            "error",
        )
    host = str(raw).strip().strip("[]").lower()
    if host in ALLOWED_BIND_HOSTS:
        return DoctorCheck("GHOST_HOST", True, str(raw).strip(), "error")
    return DoctorCheck(
        "GHOST_HOST",
        False,
        f"{raw.strip()} is not loopback; doctor requires 127.0.0.1 or localhost (0.0.0.0 / public binds fail closed)",
        "error",
    )


def _api_token_check() -> DoctorCheck:
    raw = _read_env("GHOST_API_TOKEN")
    if raw is None or not str(raw).strip():
        return DoctorCheck(
            "GHOST_API_TOKEN",
            False,
            "empty; required for API readiness (Flask token auth is not wired yet)",
            "error",
        )
    return DoctorCheck("GHOST_API_TOKEN", True, "set", "error")


def run_doctor_checks(config_override: Config | None = None) -> list[DoctorCheck]:
    """Return local readiness checks without printing or exiting.

    Exposure gates (`GHOST_SECRET_KEY`, `GHOST_HOST`, `GHOST_API_TOKEN`) fail
    closed so `ghost doctor` / `ghost doctor --json` exit non-zero on insecure
    defaults. They do not block CLI-only `investigate --authorized --no-ai`,
    which never starts Flask.
    """
    cfg = config_override or config
    checks: list[DoctorCheck] = []

    try:
        database_path = resolve_database_path(cfg.database_url) if config_override else DB_PATH
        init_db(database_path)
        with get_connection(database_path) as conn:
            conn.execute("SELECT 1").fetchone()
        checks.append(DoctorCheck("database", True, str(database_path), "error"))
    except Exception as exc:
        checks.append(DoctorCheck("database", False, str(exc), "error"))

    checks.append(_secret_key_check())
    checks.append(_host_check())
    checks.append(_api_token_check())

    checks.append(
        DoctorCheck(
            "OpenAI key",
            cfg.has_api_key("openai_api_key"),
            "set" if cfg.has_api_key("openai_api_key") else "missing; fallback summaries still work",
        )
    )

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


def summarize_doctor_checks(checks: list[DoctorCheck]) -> dict:
    """Return a machine-readable readiness summary for CLI, API, and CI use."""
    failed_errors = [check for check in checks if not check.ok and check.severity == "error"]
    warnings = [check for check in checks if not check.ok and check.severity != "error"]
    return {
        "ok": not failed_errors,
        "error_count": len(failed_errors),
        "warning_count": len(warnings),
        "checks": [
            {
                "name": check.name,
                "ok": check.ok,
                "detail": check.detail,
                "severity": check.severity,
            }
            for check in checks
        ],
    }
