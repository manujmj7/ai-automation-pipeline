"""Configuration module for the AI-Powered Assistant & Automation Pipeline.

Loads environment variables, defines model settings, browser options,
database locations, timeouts, and logging configuration.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load variables from .env file if present
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(dotenv_path=BASE_DIR / ".env")


@dataclass
class PipelineConfig:
    """Central configuration dataclass for the entire pipeline."""

    # Gemini AI configuration
    gemini_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY", "").strip() or None
    )
    gemini_model: str = field(
        default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
    )
    max_api_retries: int = field(
        default_factory=lambda: int(os.getenv("MAX_API_RETRIES", "3"))
    )
    initial_backoff_seconds: float = field(
        default_factory=lambda: float(os.getenv("INITIAL_BACKOFF_SECONDS", "2.0"))
    )

    # Scraper & Selenium configuration
    default_target_url: str = field(
        default_factory=lambda: os.getenv(
            "DEFAULT_TARGET_URL", "https://quotes.toscrape.com/"
        ).strip()
    )
    headless_browser: bool = field(
        default_factory=lambda: os.getenv("HEADLESS_BROWSER", "True").lower()
        in ("1", "true", "yes")
    )
    page_load_timeout: int = field(
        default_factory=lambda: int(os.getenv("PAGE_LOAD_TIMEOUT", "25"))
    )
    explicit_wait_timeout: int = field(
        default_factory=lambda: int(os.getenv("EXPLICIT_WAIT_TIMEOUT", "12"))
    )
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )

    # Storage and Persistence
    database_path: Path = field(
        default_factory=lambda: BASE_DIR / os.getenv("DATABASE_PATH", "pipeline_data.db")
    )
    export_json_path: Path = field(
        default_factory=lambda: BASE_DIR / os.getenv("EXPORT_JSON_PATH", "data/results.json")
    )

    def is_api_key_configured(self) -> bool:
        """Check whether a non-dummy Gemini API key is configured."""
        if not self.gemini_api_key:
            return False
        dummy_markers = ["your_gemini_api_key_here", "placeholder", "changeme", "test_key"]
        return not any(marker in self.gemini_api_key.lower() for marker in dummy_markers)


def setup_logger(name: str = "pipeline", level: int = logging.INFO) -> logging.Logger:
    """Configures and returns a structured logger."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(level)
        formatter = logging.Formatter(
            fmt="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
    return logger


# Default shared instance
default_config = PipelineConfig()
logger = setup_logger("pipeline")
