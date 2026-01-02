"""Business logic for chat functionality, extracted for better testability."""

import asyncio
import json
import re
import nltk
from typing import List, Dict, Any, Optional, AsyncGenerator
from datetime import datetime
from fastapi import HTTPException
from google.genai import types

from models import CurrentLocation, BirthData, HoroscopePeriod
# from astrology import generate_transits # Unused in simplified logic
from config import get_logger, GEMINI_API_KEY

logger = get_logger(__name__)

_PUNKT_AVAILABLE = False
_punkt_warning_logged = False

try:
    # Check once at import; we handle fallback if unavailable
    nltk.data.find("tokenizers/punkt")
    _PUNKT_AVAILABLE = True
except LookupError:
    logger.info("NLTK 'punkt' tokenizer not found; sentence counting will use regex fallback.")


def validate_user_profile(profile: Optional[Dict[str, Any]]) -> None:
    """Validate that user profile has required fields for chat.
    
    Args:
        profile: User profile data from Firestore
        
    Raises:
        HTTPException: If profile is missing required fields
    """
    if not profile:
        raise HTTPException(
            status_code=400, 
            detail="User profile not found. Please create a profile first."
        )
    
    required_fields = ['birth_date', 'birth_time', 'latitude', 'longitude', 'astrological_chart']
    missing_fields = []
    
    for field in required_fields:
        if field not in profile or profile[field] is None:
            missing_fields.append(field)
    
    if missing_fields:
        raise HTTPException(
            status_code=400,
            detail=f"Profile is incomplete. Missing: {', '.join(missing_fields)}. Please update your profile."
        )


def build_gemini_chat_history(firebase_messages: List[Dict[str, Any]]) -> List[types.Content]:
    """Convert Firebase message format to Gemini Content objects.
    
    Args:
        firebase_messages: Messages from Firebase with 'role' and 'content' fields
        
    Returns:
        List of Gemini Content objects
    """
    history = []
    if not firebase_messages:
        return history

    for msg in firebase_messages:
        role = msg.get('role')
        content = msg.get('content', '')
        
        # Map roles: user -> user, assistant -> model
        gemini_role = "user" if role == "user" else "model"
        
        if content:
            history.append(types.Content(
                role=gemini_role,
                parts=[types.Part(text=content)]
            ))
            
    return history


async def save_chat_history_to_firebase(user_id: str, messages: List[Dict[str, str]], db):
    """Save the chat history to Firebase.
    
    Args:
        user_id: User ID for Firebase storage
        messages: List of message dicts {'role': '...', 'content': '...'}
        db: Firestore database client
    """
    try:
        # Serialize the chat history
        serialized_data = {
            'messages': messages,
            'updated_at': datetime.now(),
            'message_count': len(messages)
        }
        
        # Store in Firebase under a single document
        chat_ref = db.collection('user_profiles').document(user_id).collection('chat_state').document('current')
        await asyncio.to_thread(chat_ref.set, serialized_data)
        
        logger.debug(f"Chat history saved to Firebase for user: {user_id} ({len(messages)} messages)")
        
    except Exception as e:
        logger.error(f"Error saving chat history to Firebase: {e}")
        # Don't raise - we don't want to break the chat if Firebase fails


async def load_chat_history_from_firebase(user_id: str, db) -> List[Dict[str, str]]:
    """Load chat messages from Firebase.
    
    Args:
        user_id: User ID for Firebase lookup
        db: Firestore database client
        
    Returns:
        List of message dicts or empty list
    """
    try:
        # Get the stored chat history state
        chat_ref = db.collection('user_profiles').document(user_id).collection('chat_state').document('current')
        chat_doc = await asyncio.to_thread(chat_ref.get)
        
        if not chat_doc.exists:
            logger.debug(f"No chat history found for user: {user_id}")
            return []
            
        chat_data = chat_doc.to_dict()
        if not chat_data:
            return []
            
        # Support both new format ('messages' list) and old SK format ('chat_history_state')
        if 'messages' in chat_data:
             return chat_data['messages']
                
        return []
        
    except Exception as e:
        logger.error(f"Error loading chat history from Firebase: {e}")
        return []


def validate_model_client(model_client) -> object:
    """Validate that the chat model client is available."""

    if not model_client:
        raise HTTPException(
            status_code=503,
            detail="Chat service not available - Gemini API not configured"
        )
    return model_client


def create_streaming_response_data(text_chunk: str) -> str:
    """Create SSE-formatted data chunk for streaming response.
    
    Args:
        text_chunk: Text chunk from the streaming response
        
    Returns:
        SSE-formatted data string
    """
    response_data = {'type': 'text_delta', 'data': {'delta': text_chunk}}
    return f"data: {json.dumps(response_data)}\n\n"


def create_error_response_data(error_message: str) -> str:
    """Create SSE-formatted error data chunk.
    
    Args:
        error_message: Error message to send
        
    Returns:
        SSE-formatted error data string
    """
    return f"data: {json.dumps({'type': 'error', 'data': {'error': error_message}})}\n\n"

def create_completion_response_data(full_response: str, transit_chart=None) -> str:
    """Create SSE-formatted completion data chunk.
    
    Args:
        full_response: Complete response text
        transit_chart: Optional transit chart data
        
    Returns:
        SSE-formatted completion data string
    """
    transit_data = None
    if transit_chart:
        # Convert AstrologicalChart to dict for JSON serialization
        transit_data = transit_chart.model_dump() if hasattr(transit_chart, 'model_dump') else transit_chart
    
    response_data = {
        'type': 'completion', 
        'data': {
            'response': full_response, 
            'content': full_response, 
            'transit': transit_data
        }
    }
    return f"data: {json.dumps(response_data)}\n\n"


def _regex_sentence_count(text: str) -> int:
    sentences = re.split(r'[.!?]+', text)
    return len([s for s in sentences if s.strip()])


def count_sentences(text: str) -> int:
    """Count the number of sentences in a given text using NLTK if available."""
    if not text:
        return 0

    global _PUNKT_AVAILABLE, _punkt_warning_logged

    if _PUNKT_AVAILABLE:
        try:
            sentences = nltk.sent_tokenize(text)
            return len(sentences)
        except LookupError:
            _PUNKT_AVAILABLE = False
            if not _punkt_warning_logged:
                logger.warning("NLTK 'punkt' tokenizer unavailable at runtime; using regex fallback.")
                _punkt_warning_logged = True
        except Exception as e:
            logger.error(f"Error tokenizing sentences with NLTK: {e}")
            _PUNKT_AVAILABLE = False

    return _regex_sentence_count(text)

async def get_user_token_usage(user_id: str, db) -> int:
    """Get the user's token usage from Firestore."""
    try:
        doc_ref = db.collection('token_usage').document(user_id)
        doc = await asyncio.to_thread(doc_ref.get)
        if doc.exists:
            return doc.to_dict().get('token_count', 0)
        return 0
    except Exception as e:
        logger.error(f"Error getting token usage for user {user_id}: {e}")
        return 0

async def update_user_token_usage(user_id: str, new_tokens: int, db):
    """Update the user's token usage in Firestore."""
    try:
        doc_ref = db.collection('token_usage').document(user_id)
        await asyncio.to_thread(doc_ref.set, {'token_count': new_tokens}, merge=True)
    except Exception as e:
        logger.error(f"Error updating token usage for user {user_id}: {e}")
