import os
from starlette.config import Config
from starlette.datastructures import Secret

# Initialize configuration from .env if present, falling back to environment variables
_env_file = ".env" if os.path.exists(".env") else None
config = Config(_env_file)

APP_NAME: str = config("APP_NAME", cast=str, default="PyServe AI API")
APP_VERSION: str = config("APP_VERSION", cast=str, default="0.1.0")
API_PREFIX: str = config("API_PREFIX", cast=str, default="/api")
IS_DEBUG: bool = config("IS_DEBUG", cast=bool, default=False)
ENVIRONMENT: str = config("ENVIRONMENT", cast=str, default="production").lower()
LOG_LEVEL: str = config("LOG_LEVEL", cast=str, default="INFO")

_default_origins = "http://localhost:3000,http://127.0.0.1:3000"
ALLOWED_ORIGINS: list[str] = config(
    "ALLOWED_ORIGINS",
    cast=lambda val: [origin.strip() for origin in val.split(",") if origin.strip()],
    default=_default_origins,
)

# Operational abuse-prevention limits
RATE_LIMIT_PER_MINUTE: int = config("RATE_LIMIT_PER_MINUTE", cast=int, default=60)
MAX_RATE_LIMIT_ENTRIES: int = config("MAX_RATE_LIMIT_ENTRIES", cast=int, default=10000)
MAX_REQUEST_BYTES: int = config(
    "MAX_REQUEST_BYTES", cast=int, default=65536  # 64 KB limit
)

# Network & Proxy configuration
TRUSTED_PROXIES: list[str] = config(
    "TRUSTED_PROXIES",
    cast=lambda val: [p.strip() for p in val.split(",") if p.strip()],
    default="",
)

# Security and ML model settings
API_KEY: Secret | None = config("API_KEY", cast=Secret, default=None)
DEFAULT_MODEL_PATH: str = config(
    "DEFAULT_MODEL_PATH", cast=str, default="models/sentiment.pkl"
)

# Default SHA-256 digest for verified baseline model artifact
DEFAULT_MODEL_SHA256: str = (
    "a37aa3bf39b864baef6bd0341a67fd67e941e084cd630f886d49f10ce49d3c9b"
)
EXPECTED_MODEL_SHA256: str | None = config(
    "EXPECTED_MODEL_SHA256", cast=str, default=DEFAULT_MODEL_SHA256
)

# Known insecure placeholder patterns that must never be used in production
FORBIDDEN_KEY_PATTERNS = {
    "sample_api_key",
    "placeholder",
    "change_me",
    "default",
    "test_key",
    "demo",
}


def validate_config() -> None:
    """
    Validates essential runtime configuration.
    Raises ValueError if required settings are invalid.
    """
    if ENVIRONMENT not in {"development", "test", "production"}:
        raise ValueError("ENVIRONMENT must be development, test, or production.")

    if MAX_RATE_LIMIT_ENTRIES <= 0:
        raise ValueError("MAX_RATE_LIMIT_ENTRIES must be a positive integer.")

    if ENVIRONMENT == "production":
        if API_KEY is None or len(str(API_KEY)) < 32:
            raise ValueError(
                "Production requires an API_KEY of at least 32 characters."
            )
        key_lower = str(API_KEY).lower()
        if any(pat in key_lower for pat in FORBIDDEN_KEY_PATTERNS):
            raise ValueError(
                "Production API_KEY must not use known placeholder or sample values."
            )
        if not ALLOWED_ORIGINS or "*" in ALLOWED_ORIGINS:
            raise ValueError("ALLOWED_ORIGINS must contain explicit origins, not '*'.")

        if not EXPECTED_MODEL_SHA256 or len(EXPECTED_MODEL_SHA256.strip()) != 64:
            raise ValueError(
                "Production requires a valid 64-character hex EXPECTED_MODEL_SHA256."
            )
        try:
            int(EXPECTED_MODEL_SHA256.strip(), 16)
        except ValueError:
            raise ValueError(
                "EXPECTED_MODEL_SHA256 must be a valid hexadecimal SHA-256 string."
            )

    if API_KEY is not None and not str(API_KEY).strip():
        raise ValueError("API_KEY environment variable cannot be empty.")

    if not DEFAULT_MODEL_PATH.strip():
        raise ValueError("DEFAULT_MODEL_PATH environment variable cannot be empty.")
