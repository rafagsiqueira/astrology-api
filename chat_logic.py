"""Business logic for chat functionality, extracted for better testability."""

import asyncio
import json
import re
import nltk
from typing import List, Dict, Any, Optional, AsyncGenerator
from datetime import datetime
from fastapi import HTTPException

# Semantic Kernel imports
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion
from semantic_kernel.contents import ChatHistory, ChatMessageContent, AuthorRole
from semantic_kernel.contents import ChatHistorySummarizationReducer
from semantic_kernel.functions import kernel_function

from models import CurrentLocation, BirthData, HoroscopePeriod
from astrology import generate_transits
from config import get_logger, OPENAI_API_KEY

logger = get_logger(__name__)

_PUNKT_AVAILABLE = False
_punkt_warning_logged = False

try:
    # Check once at import; we handle fallback if unavailable
    nltk.data.find("tokenizers/punkt")
    _PUNKT_AVAILABLE = True
except LookupError:
    logger.info("NLTK 'punkt' tokenizer not found; sentence counting will use regex fallback.")

# Global semantic kernel instance
_kernel = None
_chat_completion_service = None


class AstrologyPlugin:
    """Plugin providing astrological tools for the chat model."""
    
    def __init__(self, user_birth_data: BirthData, current_location: CurrentLocation):
        self.user_birth_data = user_birth_data
        self.current_location = current_location
    
    @kernel_function(
        description="Get transit aspects between the user's birth chart and current planetary positions for astrological timing guidance. Use this when the user asks about timing, current influences, what's happening now astrologically, or wants guidance about current planetary energies and how they interact with their natal chart.",
        name="get_transit"
    )
    def get_transits(self, period: HoroscopePeriod = HoroscopePeriod.week) -> str:
        """Get transit aspects for the discussed period.
        
        Args:
            period: The HoroscopePeriod relevant for the conversation.

        Returns:
            Synastry aspects as a formatted string
        """
        
        # (model, ) = generate_transits(self.user_birth_data, self.current_location, period=period)
        return ""

def get_semantic_kernel() -> Kernel:
    """Get or create the semantic kernel instance with optional astrology plugin.
    
    Args:
        birth_data: Optional user birth data for synastry calculations
        current_location: Optional current location for synastry calculations
        
    Returns:
        Semantic kernel instance
    """
    global _kernel, _chat_completion_service
    
    if _kernel is None:
        # Initialize the kernel
        _kernel = Kernel()
        
        # Add OpenAI chat completion service
        if OPENAI_API_KEY:
            _chat_completion_service = OpenAIChatCompletion(
                service_id="openai_chat",
                api_key=OPENAI_API_KEY,
                ai_model_id="gpt-4o-mini"
            )
            _kernel.add_service(_chat_completion_service)

            # Note: We use ChatHistorySummarizationReducer for conversation management
            # instead of the ConversationSummaryPlugin

            logger.debug("Semantic kernel initialized with OpenAI service")
        else:
            raise ValueError("OPENAI_API_KEY not found - cannot initialize semantic kernel")

    return _kernel


def get_chat_completion_service() -> OpenAIChatCompletion:
    """Get the chat completion service."""
    global _chat_completion_service
    
    if _chat_completion_service is None:
        get_semantic_kernel()  # Initialize if not already done
    
    if _chat_completion_service is None:
        raise ValueError("Chat completion service not initialized")
    
    return _chat_completion_service


def create_chat_history_reducer() -> ChatHistorySummarizationReducer:
    """Create a ChatHistorySummarizationReducer configured for GPT-4o mini's token limits.

    Returns:
        ChatHistorySummarizationReducer configured for optimal token management
    """
    chat_completion = get_chat_completion_service()

    # GPT-4o mini supports a large context window; keep a conservative limit
    return ChatHistorySummarizationReducer(
        service=chat_completion,
        target_count=120000,
        auto_reduce=True,
        threshold_count=10000
    )


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

def build_chat_history_from_messages(messages: List[Dict[str, str]]) -> ChatHistory:
    """Build Semantic Kernel ChatHistory from message list.
    
    Args:
        messages: List of message dictionaries with 'role' and 'content' keys
        
    Returns:
        ChatHistory object for Semantic Kernel
    """
    chat_history = ChatHistory()
    
    for msg in messages:
        role = AuthorRole.USER if msg["role"] == "user" else AuthorRole.ASSISTANT
        chat_history.add_message(
            ChatMessageContent(
                role=role,
                content=msg["content"]
            )
        )
    
    return chat_history


async def convert_firebase_messages_to_chat_history(firebase_messages: List[Dict[str, Any]]) -> ChatHistory:
    """Convert Firebase message format to Semantic Kernel ChatHistory with token reduction.
    
    Args:
        firebase_messages: Messages from Firebase with 'role' and 'content' fields
        
    Returns:
        ChatHistory object for Semantic Kernel, with automatic summarization
    """
    # Create a ChatHistorySummarizationReducer which IS a ChatHistory with auto-reduction
    chat_history = create_chat_history_reducer()
    
    # Add all messages to the summarizing chat history
    for msg in firebase_messages:
        role = AuthorRole.USER if msg.get('role') == 'user' else AuthorRole.ASSISTANT
        content = msg.get('content', '')
        
        if content:  # Only add non-empty messages
            chat_history.add_message(
                ChatMessageContent(
                    role=role,
                    content=content
                )
            )
    
    # If auto_reduce is False, we can manually trigger reduction
    if len(chat_history.messages) > chat_history.target_count:
        await chat_history.reduce()
        logger.debug(f"Chat history reduced to {len(chat_history.messages)} messages")
    
    return chat_history


async def save_chat_history_to_firebase(user_id: str, chat_history: ChatHistorySummarizationReducer, db):
    """Save the complete ChatHistorySummarizationReducer state to Firebase.
    
    Args:
        user_id: User ID for Firebase storage
        chat_history: ChatHistorySummarizationReducer to serialize
        db: Firestore database client
    """
    try:
        # Serialize the chat history to a dict (exclude service as it can't be serialized)
        serialized_data = {
            'chat_history_state': chat_history.serialize(),
            'updated_at': datetime.now(),
            'message_count': len(chat_history.messages)
        }
        
        # Store in Firebase under a single document
        chat_ref = db.collection('user_profiles').document(user_id).collection('chat_state').document('current')
        await asyncio.to_thread(chat_ref.set, serialized_data)
        
        logger.debug(f"Chat history saved to Firebase for user: {user_id} ({len(chat_history.messages)} messages)")
        
    except Exception as e:
        logger.error(f"Error saving chat history to Firebase: {e}")
        # Don't raise - we don't want to break the chat if Firebase fails


async def load_chat_history_from_firebase(user_id: str, db) -> Optional[ChatHistorySummarizationReducer]:
    """Load ChatHistorySummarizationReducer state from Firebase.
    
    Args:
        user_id: User ID for Firebase lookup
        db: Firestore database client
        
    Returns:
        ChatHistorySummarizationReducer or None if not found
    """
    try:
        # Get the stored chat history state
        chat_ref = db.collection('user_profiles').document(user_id).collection('chat_state').document('current')
        chat_doc = await asyncio.to_thread(chat_ref.get)
        
        if not chat_doc.exists:
            logger.debug(f"No chat history found for user: {user_id}")
            return None
            
        chat_data = chat_doc.to_dict()
        if not chat_data or 'chat_history_state' not in chat_data:
            logger.debug(f"Invalid chat history data for user: {user_id}")
            return None
            
        # Deserialize the chat history
        chat_history_state = chat_data['chat_history_state']
        if isinstance(chat_history_state, str):
            try:
                chat_history_state = json.loads(chat_history_state)
            except json.JSONDecodeError:
                logger.error("Stored chat history state is not valid JSON for user: %s", user_id)
                return None
        elif not isinstance(chat_history_state, dict):
            logger.error("Chat history state has unexpected type (%s) for user: %s", type(chat_history_state), user_id)
            return None
        else:
            chat_history_state = dict(chat_history_state)  # shallow copy so we can inject service
        
        # Recreate the ChatHistorySummarizationReducer with the service
        chat_completion = get_chat_completion_service()
        chat_history_state['service'] = chat_completion  # Re-inject the service
        
        restored_history = ChatHistorySummarizationReducer(**chat_history_state)
        
        logger.debug(f"Chat history loaded from Firebase for user: {user_id} ({len(restored_history.messages)} messages)")
        return restored_history
        
    except Exception as e:
        logger.error(f"Error loading chat history from Firebase: {e}")
        return None


def validate_model_client(model_client) -> object:
    """Validate that the chat model client is available."""

    if not model_client:
        raise HTTPException(
            status_code=503,
            detail="Chat service not available - OpenAI API not configured"
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
