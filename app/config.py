"""
Configuration management with environment variables.
"""

import os
import sys
from typing import Optional, Tuple, Dict, Any
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
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
    GITHUB_TOKEN: Optional[str] = os.getenv("GITHUB_TOKEN")

    # Model Configuration
    LLM_MAX_RETRIES: Optional[str] = os.getenv("LLM_MAX_RETRIES")
    LLM_TIMEOUT: Optional[str] = os.getenv("LLM_TIMEOUT")

    DECISION_MODEL: Optional[str] = os.getenv("DECISION_MODEL")
    CRITIC_MODEL: Optional[str] = os.getenv("CRITIC_MODEL")
    OPTIMISER_MODEL: Optional[str] = os.getenv("OPTIMISER_MODEL")
    RISK_MODEL: Optional[str] = os.getenv("RISK_MODEL")

    DECISION_MODEL_TEMPERATURE: Optional[str] = os.getenv("DECISION_MODEL_TEMPERATURE")
    CRITIC_MODEL_TEMPERATURE: Optional[str] = os.getenv("CRITIC_MODEL_TEMPERATURE")
    OPTIMISER_MODEL_TEMPERATURE: Optional[str] = os.getenv("OPTIMISER_MODEL_TEMPERATURE")
    RISK_MODEL_TEMPERATURE: Optional[str] = os.getenv("RISK_MODEL_TEMPERATURE")

    DECISION_MODEL_TOKEN: Optional[str] = os.getenv("DECISION_MODEL_TOKEN")
    CRITIC_MODEL_TOKEN: Optional[str] = os.getenv("CRITIC_MODEL_TOKEN")
    OPTIMISER_MODEL_TOKEN: Optional[str] = os.getenv("OPTIMISER_MODEL_TOKEN")
    RISK_MODEL_TOKEN: Optional[str] = os.getenv("RISK_MODEL_TOKEN")

    # Critic Thresholds
    CRITIC_DEFAULT_QUALITY_SCORE: Optional[str] = os.getenv("CRITIC_DEFAULT_QUALITY_SCORE", "7")
    CRITIC_REGRESSION_PENALTY: Optional[str] = os.getenv("CRITIC_REGRESSION_PENALTY", "0.05")
    CRITIC_UNRESOLVED_PENALTY: Optional[str] = os.getenv("CRITIC_UNRESOLVED_PENALTY", "0.02")

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
    # SSL_CERT_FILE: Optional[str] = os.getenv("SSL_CERT_FILE")
    # REQUESTS_CA_BUNDLE: Optional[str] = os.getenv("REQUESTS_CA_BUNDLE")
    SSL_CERT_FILE: Optional[str] = os.getenv("SSL_CERT_FILE") if not IS_LOCAL else None
    REQUESTS_CA_BUNDLE: Optional[str] = os.getenv("REQUESTS_CA_BUNDLE") if not IS_LOCAL else None

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
            "ANTHROPIC_API_KEY": cls.ANTHROPIC_API_KEY,
            "GITHUB_TOKEN": cls.GITHUB_TOKEN,

            # Models / LLM configuration
            "DECISION_MODEL": cls.DECISION_MODEL,
            "CRITIC_MODEL": cls.CRITIC_MODEL,
            "OPTIMISER_MODEL": cls.OPTIMISER_MODEL,
            "RISK_MODEL": cls.RISK_MODEL,

            "DECISION_MODEL_TEMPERATURE": cls.DECISION_MODEL_TEMPERATURE,
            "CRITIC_MODEL_TEMPERATURE": cls.CRITIC_MODEL_TEMPERATURE,
            "OPTIMISER_MODEL_TEMPERATURE": cls.OPTIMISER_MODEL_TEMPERATURE,
            "RISK_MODEL_TEMPERATURE": cls.RISK_MODEL_TEMPERATURE,

            "DECISION_MODEL_TOKEN": cls.DECISION_MODEL_TOKEN,
            "CRITIC_MODEL_TOKEN": cls.CRITIC_MODEL_TOKEN,
            "OPTIMISER_MODEL_TOKEN": cls.OPTIMISER_MODEL_TOKEN,
            "RISK_MODEL_TOKEN": cls.RISK_MODEL_TOKEN,

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
            cls.LLM_MAX_RETRIES = int(cls.LLM_MAX_RETRIES)
            cls.LLM_TIMEOUT = int(cls.LLM_TIMEOUT)

            cls.DECISION_MODEL_TEMPERATURE = float(cls.DECISION_MODEL_TEMPERATURE)
            cls.CRITIC_MODEL_TEMPERATURE = float(cls.CRITIC_MODEL_TEMPERATURE)
            cls.OPTIMISER_MODEL_TEMPERATURE = float(cls.OPTIMISER_MODEL_TEMPERATURE)
            cls.RISK_MODEL_TEMPERATURE = float(cls.RISK_MODEL_TEMPERATURE)

            cls.DECISION_MODEL_TOKEN = int(cls.DECISION_MODEL_TOKEN)
            cls.CRITIC_MODEL_TOKEN = int(cls.CRITIC_MODEL_TOKEN)
            cls.OPTIMISER_MODEL_TOKEN = int(cls.OPTIMISER_MODEL_TOKEN)
            cls.RISK_MODEL_TOKEN = int(cls.RISK_MODEL_TOKEN)

            cls.CRITIC_DEFAULT_QUALITY_SCORE = int(cls.CRITIC_DEFAULT_QUALITY_SCORE)
            cls.CRITIC_REGRESSION_PENALTY = float(cls.CRITIC_REGRESSION_PENALTY)
            cls.CRITIC_UNRESOLVED_PENALTY = float(cls.CRITIC_UNRESOLVED_PENALTY)

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

    # Agent Configuration Methods
    @classmethod
    def get_decision_config(cls) -> Dict[str, Any]:
        """Get configuration for Decision agent."""
        return {
            "model": cls.DECISION_MODEL,
            "temperature": cls.DECISION_MODEL_TEMPERATURE,
            "max_tokens": cls.DECISION_MODEL_TOKEN
        }
    
    @classmethod
    def get_optimiser_config(cls) -> Dict[str, Any]:
        """Get configuration for Optimiser agent."""
        return {
            "model": cls.OPTIMISER_MODEL,
            "temperature": cls.OPTIMISER_MODEL_TEMPERATURE,
            "max_tokens": cls.OPTIMISER_MODEL_TOKEN
        }
    
    @classmethod
    def get_critic_config(cls) -> Dict[str, Any]:
        """Get configuration for Critic agent."""
        return {
            "model": cls.CRITIC_MODEL,
            "temperature": cls.CRITIC_MODEL_TEMPERATURE,
            "max_tokens": cls.CRITIC_MODEL_TOKEN,
            "default_quality_score": cls.CRITIC_DEFAULT_QUALITY_SCORE,
            "regression_penalty": cls.CRITIC_REGRESSION_PENALTY,
            "unresolved_penalty": cls.CRITIC_UNRESOLVED_PENALTY
        }
    
    @classmethod
    def get_risk_config(cls) -> Dict[str, Any]:
        """Get configuration for Risk Assessor agent."""
        return {
            "model": cls.RISK_MODEL,
            "temperature": cls.RISK_MODEL_TEMPERATURE,
            "max_tokens": cls.RISK_MODEL_TOKEN
        }


config = Config()

try:
    config.validate()
    logger.debug("Configuration successfully loaded and validated")
except SystemExit:
    sys.exit(1)
except Exception:
    logger.exception("Unexpected error during configuration validation")
    sys.exit(1)