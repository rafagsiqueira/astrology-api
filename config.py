"""Configuration module for Avra backend."""

import logging
import os

from dotenv import load_dotenv
from kerykeion.utilities import setup_logging  # noqa: F401  # Ensures logging configuration for kerykeion

# Load environment variables from .env file if present
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Suppress verbose logs from third-party libraries
logging.getLogger('openai').setLevel(logging.INFO)
logging.getLogger('httpx').setLevel(logging.INFO)
logging.getLogger('httpcore').setLevel(logging.INFO)
logging.getLogger('root').setLevel(logging.INFO)

logger = logging.getLogger(__name__)

# Environment variables
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
FIRESTORE_DATABASE_ID = os.getenv('FIRESTORE_DATABASE_ID')

# App configuration
APP_TITLE = "Avra API"
APP_VERSION = "1.0.0"

# CORS configuration
CORS_ORIGINS = ["*"]  # In production, specify your Flutter app's domain
CORS_CREDENTIALS = True
CORS_METHODS = ["*"]
CORS_HEADERS = ["*"]


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the specified name."""
    return logging.getLogger(name)


def get_openai_client():
    """Initialise the OpenAI client if the API key is configured."""
    try:
        if OPENAI_API_KEY:
            from openai import OpenAI
            return OpenAI(api_key=OPENAI_API_KEY)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error(f"Failed to initialise OpenAI client: {exc}")
    return None
