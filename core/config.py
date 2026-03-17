"""Ghost configuration management."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Define base directory and data directories
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
INVESTIGATIONS_DIR = BASE_DIR / "investigations"

# Create data directories if they do not exist
DATA_DIR.mkdir(exist_ok=True)
INVESTIGATIONS_DIR.mkdir(exist_ok=True)


@dataclass
class GhostConfig:
    """
    Central configuration for Ghost platform.

    Attributes:
        openai_api_key (str): OpenAI API key
        openai_model (str): OpenAI model
        hibp_api_key (str): Have I Been Pwned API key
        shodan_api_key (str): Shodan API key
        google_api_key (str): Google API key
        google_cx (str): Google Custom Search Engine ID
        twitter_bearer_token (str): Twitter Bearer Token
        ipinfo_token (str): IPInfo API token
        hunter_api_key (str): Hunter API key
        fullcontact_api_key (str): FullContact API key
        host (str): Host IP address
        port (int): Host port
        debug (bool): Debug mode
        secret_key (str): Secret key for encryption
        database_url (str): Database URL
        rate_limit_requests (int): Rate limit requests per period
        rate_limit_period (int): Rate limit period in seconds
        enabled_modules (list): List of enabled modules
        request_timeout (int): Request timeout in seconds
        max_concurrent_requests (int): Maximum concurrent requests
        user_agent (str): User agent string
    """

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

    # Server
    host: str = os.getenv("GHOST_HOST", "0.0.0.0")
    port: int = int(os.getenv("GHOST_PORT", "5000"))
    debug: bool = os.getenv("GHOST_DEBUG", "false").lower() == "true"
    secret_key: str = os.getenv("GHOST_SECRET_KEY", "ghost-dev-key")

    # Database
    database_url: str = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'ghost.db'}")

    # Rate limiting
    rate_limit_requests: int = int(os.getenv("RATE_LIMIT_REQUESTS", "60"))
    rate_limit_period: int = int(os.getenv("RATE_LIMIT_PERIOD", "60"))

    # Module toggles
    enabled_modules: list = field(
        default_factory=lambda: [
            "username",
            "email",
            "phone",
            "social",
            "domain",
            "image",
            "darkweb",
            "geolocation",
        ]
    )

    # Request settings
    request_timeout: int = 30
    max_concurrent_requests: int = 20
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

    def has_api_key(self, key_name: str) -> bool:
        """
        Check if the configuration has a specific API key.

        Args:
            key_name (str): Name of the API key to check

        Returns:
            bool: True if the API key exists, False otherwise
        """
        return bool(getattr(self, key_name, ""))


# Create a GhostConfig instance
config = GhostConfig()
