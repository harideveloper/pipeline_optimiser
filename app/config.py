"""
Configuration management with environment variables.
Fail-fast on missing critical configuration.
"""

import os
import sys
from typing import Optional
from dotenv import load_dotenv
from app.utils.logger import get_logger

# Load .env file early (for local/dev)
load_dotenv()

logger = get_logger(__name__, "Configuration")


class Config:
    """Application configuration loaded from environment variables."""

    # General
    IS_LOCAL = os.getenv("IS_LOCAL", "false").lower() == "true"

    # API Keys
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
    GITHUB_TOKEN: Optional[str] = os.getenv("GITHUB_TOKEN")

    # Model Configuration
    MODEL_NAME: Optional[str] = os.getenv("MODEL_NAME")
    MODEL_TEMPERATURE: Optional[str] = os.getenv("MODEL_TEMPERATURE")
    ANALYSER_MODEL: Optional[str] = os.getenv("ANALYSER_MODEL")
    RISK_ASSESSOR_MODEL: Optional[str] = os.getenv("RISK_ASSESSOR_MODEL")
    LLM_MAX_RETRIES: Optional[str] = os.getenv("LLM_MAX_RETRIES")
    LLM_TIMEOUT: Optional[str] = os.getenv("LLM_TIMEOUT")

    # Database Configuration
    DB_HOST: Optional[str] = os.getenv("DB_HOST")
    DB_PORT: Optional[str] = os.getenv("DB_PORT")
    DB_NAME: Optional[str] = os.getenv("DB_NAME")
    DB_USER: Optional[str] = os.getenv("DB_USER")
    DB_PASS: Optional[str] = os.getenv("DB_PASS")
    DB_POOL_SIZE: Optional[str] = os.getenv("DB_POOL_SIZE")
    DB_MAX_OVERFLOW: Optional[str] = os.getenv("DB_MAX_OVERFLOW")

    # Application Settings
    API_HOST: Optional[str] = os.getenv("API_HOST")
    API_PORT: Optional[str] = os.getenv("API_PORT")
    LOG_LEVEL: Optional[str] = os.getenv("LOG_LEVEL")
    LOG_FILE: Optional[str] = os.getenv("LOG_FILE")

    # SSL / Certificates
    SSL_CERT_FILE: Optional[str] = os.getenv("SSL_CERT_FILE")
    REQUESTS_CA_BUNDLE: Optional[str] = os.getenv("REQUESTS_CA_BUNDLE")

    # Git & Workflow Configuration
    GIT_CLONE_DEPTH: Optional[str] = os.getenv("GIT_CLONE_DEPTH")
    GIT_TIMEOUT: Optional[str] = os.getenv("GIT_TIMEOUT")
    MAX_PLAN_TOOLS: Optional[str] = os.getenv("MAX_PLAN_TOOLS")
    ENABLE_PARALLEL_EXECUTION: Optional[str] = os.getenv("ENABLE_PARALLEL_EXECUTION")


    # Validation
    @classmethod
    def validate(cls) -> None:
        """Validate required environment variables and convert types."""
        required_vars = {
            # Core credentials
            "OPENAI_API_KEY": cls.OPENAI_API_KEY,
            "ANTHROPIC_API_KEY": cls.ANTHROPIC_API_KEY,
            "GITHUB_TOKEN": cls.GITHUB_TOKEN,

            # Models / LLM configuration
            "MODEL_NAME": cls.MODEL_NAME,
            "MODEL_TEMPERATURE": cls.MODEL_TEMPERATURE,
            "ANALYSER_MODEL": cls.ANALYSER_MODEL,
            "RISK_ASSESSOR_MODEL": cls.RISK_ASSESSOR_MODEL,
            "LLM_MAX_RETRIES": cls.LLM_MAX_RETRIES,
            "LLM_TIMEOUT": cls.LLM_TIMEOUT,

            # Database configuration
            "DB_HOST": cls.DB_HOST,
            "DB_PORT": cls.DB_PORT,
            "DB_NAME": cls.DB_NAME,
            "DB_USER": cls.DB_USER,
            "DB_PASS": cls.DB_PASS,

            # App configuration
            "API_HOST": cls.API_HOST,
            "API_PORT": cls.API_PORT,
            "LOG_LEVEL": cls.LOG_LEVEL,

            # Git/Workflow settings
            "GIT_CLONE_DEPTH": cls.GIT_CLONE_DEPTH,
            "GIT_TIMEOUT": cls.GIT_TIMEOUT,
            "MAX_PLAN_TOOLS": cls.MAX_PLAN_TOOLS,
            "ENABLE_PARALLEL_EXECUTION": cls.ENABLE_PARALLEL_EXECUTION,
        }

        # Fail fast if any required var is missing
        missing = [name for name, value in required_vars.items() if value is None]
        if missing:
            logger.critical(
                "Missing required configuration:\n  - " + "\n  - ".join(missing)
            )
            raise SystemExit(1)

        
        # Convert numeric and boolean types
        try:
            cls.MODEL_TEMPERATURE = float(cls.MODEL_TEMPERATURE)
            cls.LLM_MAX_RETRIES = int(cls.LLM_MAX_RETRIES)
            cls.LLM_TIMEOUT = int(cls.LLM_TIMEOUT)

            cls.DB_PORT = int(cls.DB_PORT)
            cls.DB_POOL_SIZE = int(cls.DB_POOL_SIZE)
            cls.DB_MAX_OVERFLOW = int(cls.DB_MAX_OVERFLOW)

            cls.API_PORT = int(cls.API_PORT)

            cls.GIT_CLONE_DEPTH = int(cls.GIT_CLONE_DEPTH)
            cls.GIT_TIMEOUT = int(cls.GIT_TIMEOUT)
            cls.MAX_PLAN_TOOLS = int(cls.MAX_PLAN_TOOLS)
            cls.ENABLE_PARALLEL_EXECUTION = cls.ENABLE_PARALLEL_EXECUTION.lower() == "true"
        except Exception as e:
            logger.critical(f"Invalid type in environment variables: {e}")
            raise SystemExit(1)

        logger.info("All required environment variables validated and types converted successfully")

        # Optional vars: warn if missing
        if not cls.SSL_CERT_FILE:
            logger.warning("SSL_CERT_FILE not set — using system defaults")


    @classmethod
    def get_db_connection_string(cls) -> str:
        """Return PostgreSQL connection string."""
        conn_str = (
            f"postgresql://{cls.DB_USER}:{cls.DB_PASS}"
            f"@{cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_NAME}"
        )
        logger.debug(
            "Constructed DB connection string",
            extra={"db_host": cls.DB_HOST, "db_name": cls.DB_NAME},
        )
        return conn_str



# Runtime Validation for env vars
config = Config()

try:
    config.validate()
    logger.debug("Configuration successfully loaded and validated")
except SystemExit:
    sys.exit(1)
except Exception:
    logger.exception("Unexpected error during configuration validation")
    sys.exit(1)
