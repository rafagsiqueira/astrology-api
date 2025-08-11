"""Configuration module for Cosmic Guru backend."""

import os
import logging
from dotenv import load_dotenv
from kerykeion.utilities import setup_logging

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Suppress debug logs from third-party libraries
logging.getLogger('anthropic._base_client').setLevel(logging.INFO)
logging.getLogger('anthropic').setLevel(logging.INFO)
logging.getLogger('httpx').setLevel(logging.INFO)
logging.getLogger('httpcore').setLevel(logging.INFO)
logging.getLogger('root').setLevel(logging.INFO)

logger = logging.getLogger(__name__)

# Environment variables
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
FIRESTORE_DATABASE_ID = os.getenv('FIRESTORE_DATABASE_ID')

# App configuration
APP_TITLE = "Cosmic Guru API"
APP_VERSION = "1.0.0"

# CORS configuration
CORS_ORIGINS = ["*"]  # In production, specify your Flutter app's domain
CORS_CREDENTIALS = True
CORS_METHODS = ["*"]
CORS_HEADERS = ["*"]

# Logging configuration
def get_logger(name: str) -> logging.Logger:
	"""Get a logger instance with the specified name."""
	return logging.getLogger(name)

# Initialize Claude API client
def get_claude_client():
	"""Initialize the Claude API client if the API key is set."""
	try:
		if ANTHROPIC_API_KEY:
			import anthropic
			return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
	except Exception as e:
		logger.error(f"Failed to initialize Claude API client: {e}")
	return None