"""Ghost configuration management."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
INVESTIGATIONS_DIR = BASE_DIR / "investigations"

DATA_DIR.mkdir(exist_ok=True)
INVESTIGATIONS_DIR.mkdir(exist_ok=True)

# Placeholders that must never ship as a non-debug Flask secret.
INSECURE_SECRET_DEFAULTS = frozenset(
    {
        "ghost-dev-key",
        "change-this-to-a-random-string",
        "changeme",
        "secret",
        "secret-key",
        "dev-key",
        "development",
    }
)


def _env_or(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value


def is_insecure_secret_key(value: str | None) -> bool:
    """Return True when a secret is missing or a known shippable placeholder."""
    if value is None:
        return True
    stripped = value.strip()
    if not stripped:
        return True
    return stripped.lower() in INSECURE_SECRET_DEFAULTS


def validate_secret_key(secret_key: str | None, *, debug: bool) -> None:
    """Reject missing/placeholder GHOST_SECRET_KEY outside debug."""
    if debug:
        return
    if is_insecure_secret_key(secret_key):
        raise ValueError(
            "GHOST_SECRET_KEY is required outside debug and must not be an insecure "
            "default (for example 'ghost-dev-key'). Set a random value in .env."
        )


def validate_api_token(api_token: str | None) -> None:
    """Reject a missing Flask API token. CLI-only use does not require this."""
    if not (api_token or "").strip():
        raise ValueError(
            "GHOST_API_TOKEN is required to start the Flask API. "
            "Clients must send Authorization: Bearer <token> or X-Ghost-Token."
        )


def validate_flask_runtime(cfg: "Config") -> None:
    """Fail closed before the Flask server binds a port."""
    validate_secret_key(cfg.secret_key, debug=cfg.debug)
    validate_api_token(cfg.api_token)


@dataclass
class Config:
    """Central configuration for Ghost platform."""

    # AI
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o")

    # APIs
    hibp_api_key: str = os.getenv("HIBP_API_KEY", "")
    shodan_api_key: str = os.getenv("SHODAN_API_KEY", "")
    google_api_key: str = os.getenv("GOOGLE_API_KEY", "")
    google_cx: str = os.getenv("GOOGLE_CX", "")
    twitter_bearer_token: str = os.getenv("TWITTER_BEARER_TOKEN", "")
    ipinfo_token: str = os.getenv("IPINFO_TOKEN", "")
    hunter_api_key: str = os.getenv("HUNTER_API_KEY", "")
    fullcontact_api_key: str = os.getenv("FULLCONTACT_API_KEY", "")

    # Server — bind loopback by default; do not ship 0.0.0.0 as the app default.
    # Doctor still treats unset GHOST_HOST as CLI-only OK; Flask uses 127.0.0.1.
    host: str = field(default_factory=lambda: _env_or("GHOST_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(_env_or("GHOST_PORT", "5000")))
    debug: bool = field(default_factory=lambda: os.getenv("GHOST_DEBUG", "false").lower() == "true")
    secret_key: str = field(default_factory=lambda: os.getenv("GHOST_SECRET_KEY", ""))
    api_token: str = field(default_factory=lambda: os.getenv("GHOST_API_TOKEN", ""))

    # Database
    database_url: str = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'ghost.db'}")

    # Rate limiting — enforced on /api/* (except /api/health)
    rate_limit_requests: int = field(default_factory=lambda: int(_env_or("RATE_LIMIT_REQUESTS", "60")))
    rate_limit_period: int = field(default_factory=lambda: int(_env_or("RATE_LIMIT_PERIOD", "60")))

    # Module toggles
    enabled_modules: list = field(
        default_factory=lambda: ["username", "email", "phone", "domain", "image", "geolocation"]
    )

    # Request settings
    request_timeout: int = 30
    max_concurrent_requests: int = 20
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

    def has_api_key(self, key_name: str) -> bool:
        return bool(getattr(self, key_name, ""))


config = Config()
