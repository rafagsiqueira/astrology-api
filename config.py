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
logging.getLogger('httpx').setLevel(logging.INFO)
logging.getLogger('httpcore').setLevel(logging.INFO)
logging.getLogger('root').setLevel(logging.INFO)

logger = logging.getLogger(__name__)

# Environment variables
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')  # Add Gemini API Key
PROJECT_ID = os.getenv('PROJECT_ID')
LOCATION = os.getenv('LOCATION')
FIRESTORE_DATABASE_ID = os.getenv('FIRESTORE_DATABASE_ID')
WEATHERKIT_TEAM_ID = os.getenv('WEATHERKIT_TEAM_ID', 'F957AP9B34')
WEATHERKIT_KEY_ID = os.getenv('WEATHERKIT_KEY_ID', '4PDNV2USTN')
WEATHERKIT_SERVICE_ID = os.getenv('WEATHERKIT_SERVICE_ID', 'com.rafasiqueira.avra.weatherkit-client')
WEATHERKIT_KEY_PATH = os.getenv('WEATHERKIT_KEY_PATH')
GCS_AUDIO_BUCKET = os.getenv('GCS_AUDIO_BUCKET')

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


class VertexAIAdapter:
    """Adapter to make vertexai SDK look like google.genai Client."""
    def __init__(self, project: str, location: str):
        import vertexai
        vertexai.init(project=project, location=location)
        self.models = self
        
    def generate_content(self, model: str, contents, config=None, **kwargs):
        from vertexai.generative_models import GenerativeModel, GenerationConfig
        
        # Handle system instruction from config
        system_instruction = None
        if config and hasattr(config, 'system_instruction'):
            system_instruction = config.system_instruction
            
        gemini_model = GenerativeModel(model, system_instruction=system_instruction)
        
        # Build generation config
        generation_config_args = {}
        if config:
            if hasattr(config, 'max_output_tokens'):
                generation_config_args['max_output_tokens'] = config.max_output_tokens
            if hasattr(config, 'response_mime_type'):
                generation_config_args['response_mime_type'] = config.response_mime_type
            if hasattr(config, 'response_schema'):
                # Convert Pydantic model to JSON schema dict for Vertex AI
                schema = config.response_schema
                if hasattr(schema, 'model_json_schema'):
                    generation_config_args['response_schema'] = schema.model_json_schema()
                else:
                    generation_config_args['response_schema'] = schema

        return gemini_model.generate_content(
            contents,
            generation_config=GenerationConfig(**generation_config_args)
        )

def get_gemini_client():
    """Initialise the Google Gemini client if the API key is configured."""
    try:
        if GEMINI_API_KEY:
            # Patch SDK before use to fix timeout bug
            from genai_patch import apply_patch
            apply_patch()
            
            from google import genai
            from google.genai import types
            logger.info("Applying custom timeout of 60s to Gemini Client via patch")
            return genai.Client(
                api_key=GEMINI_API_KEY,
                http_options=types.HttpOptions(timeout=60000) 
            )
        else:
            if not PROJECT_ID or not LOCATION:
                 logger.error("GEMINI_API_KEY not found, and PROJECT_ID/LOCATION not set for Vertex AI")
                 return None

            logger.info(f"Using Vertex AI SDK with project={PROJECT_ID}, location={LOCATION}")
            return VertexAIAdapter(project=PROJECT_ID, location=LOCATION)
            
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error(f"Failed to initialise Gemini client: {exc}")
    return None

