import unittest
import json
import asyncio
import sys
from unittest.mock import Mock, patch, AsyncMock
from fastapi import HTTPException

# Mock semantic_kernel modules before importing chat_logic
sys.modules['semantic_kernel'] = Mock()
sys.modules['semantic_kernel.connectors.ai.open_ai'] = Mock()
sys.modules['semantic_kernel.contents'] = Mock()
sys.modules['semantic_kernel.functions'] = Mock()

from chat_logic import (
    validate_user_profile,
    build_gemini_chat_history, create_streaming_response_data,
    create_error_response_data,
    count_sentences
)
from contexts import build_chat_context
from models import ChatRequest, ChatMessage, CurrentLocation
from semantic_kernel.contents import AuthorRole
import routes

class TestChatBusinessLogic(unittest.TestCase):
    """Test suite for chat business logic functions"""

    def test_validate_user_profile_valid(self):
        """Test profile validation with valid profile"""
        valid_profile = {
            'birth_date': '1990-01-01',
            'birth_time': '12:00',
            'latitude': 40.7128,
            'longitude': -74.0060,
            'timezone': 'America/New_York',
            'astrological_chart': {'planets': {}, 'aspects': []}
        }

        try:
            validate_user_profile(valid_profile)
        except HTTPException:
            self.fail("validate_user_profile() raised HTTPException unexpectedly!")

    def test_validate_user_profile_missing(self):
        """Test profile validation with missing profile"""
        with self.assertRaises(HTTPException) as cm:
            validate_user_profile(None)

        self.assertEqual(cm.exception.status_code, 400)
        self.assertIn("User profile not found", cm.exception.detail)

    def test_validate_user_profile_incomplete(self):
        """Test profile validation with incomplete profile"""
        incomplete_profile = {
            'birth_date': '1990-01-01',
            'birth_time': None,
            'latitude': 40.7128,
            'timezone': 'America/New_York'
        }

        with self.assertRaises(HTTPException) as cm:
            validate_user_profile(incomplete_profile)

        self.assertEqual(cm.exception.status_code, 400)
        self.assertIn("Profile is incomplete", cm.exception.detail)
        self.assertIn("birth_time", cm.exception.detail)
        self.assertIn("longitude", cm.exception.detail)

    def test_build_chat_context_with_data(self):
        """Test chat context building with astrological data"""
        context_data = {
            "birth_chart": "Sun in Aquarius, Moon in Gemini...",
            "current_data": "Mars in Leo, Venus in Virgo..."
        }

        system, user = build_chat_context(context_data)

        self.assertIn("knowledgeable and friendly astrologer", system)
        self.assertIn("birth_chart", user)
        self.assertIn("horoscope", user)
        self.assertIn("personality_analysis", user)
        self.assertIn("relationships", user)

    def test_build_chat_context_without_data(self):
        """Test chat context building without astrological data"""
        system, user = build_chat_context({})

        self.assertIn("knowledgeable and friendly astrologer", system)
        self.assertIn("No birth chart data available", user)

    def test_build_gemini_chat_history(self):
        """Test conversion of Firebase messages to Gemini Content objects"""
        from google.genai import types

        firebase_messages = [
            {"role": "user", "content": "What's my sign?"},
            {"role": "assistant", "content": "You're an Aquarius."},
            {"role": "user", "content": "Tell me more about it."}
        ]

        chat_history = build_gemini_chat_history(firebase_messages)

        self.assertEqual(len(chat_history), 3)
        self.assertIsInstance(chat_history[0], types.Content)
        self.assertEqual(chat_history[0].role, "user")
        self.assertEqual(chat_history[0].parts[0].text, "What's my sign?")
        
        self.assertEqual(chat_history[1].role, "model")
        self.assertEqual(chat_history[1].parts[0].text, "You're an Aquarius.")

        self.assertEqual(chat_history[2].role, "user")
        self.assertEqual(chat_history[2].parts[0].text, "Tell me more about it.")

    def test_create_streaming_response_data(self):
        """Test SSE data formatting for streaming response"""
        text_chunk = "Hello, this is a response chunk."

        result = create_streaming_response_data(text_chunk)

        self.assertTrue(result.startswith("data: "))
        self.assertTrue(result.endswith("\n\n"))

        json_part = result[6:-2]
        data = json.loads(json_part)
        self.assertEqual(data["type"], "text_delta")
        self.assertEqual(data["data"]["delta"], text_chunk)

    def test_create_error_response_data(self):
        """Test SSE error data formatting"""
        error_message = "Something went wrong"

        result = create_error_response_data(error_message)

        self.assertTrue(result.startswith("data: "))
        self.assertTrue(result.endswith("\n\n"))

        json_part = result[6:-2]
        data = json.loads(json_part)
        self.assertEqual(data["type"], "error")
        self.assertEqual(data["data"]["error"], error_message)

if __name__ == '__main__':
    unittest.main()

class TestTokenLimiting(unittest.TestCase):
    """Test suite for token limiting functionality"""



    @patch('routes.get_gemini_client')
    @patch('routes.load_chat_history_from_firebase')
    @patch('routes.validate_user_profile')
    @patch('routes.get_user_profile_cached')
    @patch('routes.get_firestore_client')
    @patch('routes.get_subscription_service')
    @patch('routes.validate_database_availability')
    @patch('routes.get_analytics_service')
    def test_chat_with_guru_with_subscription(self, mock_get_analytics, mock_validate_db, mock_get_sub_service, mock_get_db, mock_get_profile, mock_validate_profile, mock_load_history, mock_get_gemini):
        """Test chat with a subscription"""
        async def run_test():
            mock_get_analytics.return_value = AsyncMock()
            mock_get_sub_service.return_value.has_premium_access = AsyncMock(return_value=True)

            request = ChatRequest(message="Hello")
            user = {'uid': 'test-user'}

            # Mock Gemini client chat stream
            class AsyncIterator:
                def __init__(self, seq):
                    self.iter = iter(seq)
                def __aiter__(self):
                    return self
                async def __anext__(self):
                    try:
                        return next(self.iter)
                    except StopIteration:
                        raise StopAsyncIteration

            mock_chat = Mock()
            mock_stream = AsyncIterator([Mock(text="Hello world")])
            mock_chat.send_message_stream = AsyncMock(return_value=mock_stream)
            mock_get_gemini.return_value.aio.chats.create.return_value = mock_chat

            response = await routes.chat_with_guru(request, user)
            
            # Consume the stream to ensure logic runs
            async for _ in response.body_iterator:
                pass
            
            mock_get_sub_service.return_value.has_premium_access.assert_called()

        asyncio.run(run_test())
