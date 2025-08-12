import unittest
import json
import asyncio
from unittest.mock import Mock, patch
from fastapi import HTTPException

from chat_logic import (
    validate_user_profile,
    convert_firebase_messages_to_chat_history, create_streaming_response_data,
    create_error_response_data
)
from contexts import build_chat_context
from models import ChatMessage, CurrentLocation
from semantic_kernel.contents import AuthorRole

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

        self.assertIn("knowledgeable and friendly cosmicloger", system)
        self.assertIn("birth_chart", user)
        self.assertIn("horoscope", user)
        self.assertIn("personality_analysis", user)
        self.assertIn("relationships", user)

    def test_build_chat_context_without_data(self):
        """Test chat context building without astrological data"""
        system, user = build_chat_context({})

        self.assertIn("knowledgeable and friendly cosmicloger", system)
        self.assertIn("No birth chart data available", user)

    def test_convert_firebase_messages_to_chat_history(self):
        """Test conversion of Firebase messages to Semantic Kernel ChatHistory"""
        async def run_test():
            firebase_messages = [
                {"role": "user", "content": "What's my sign?"},
                {"role": "assistant", "content": "You're an Aquarius."},
                {"role": "user", "content": "Tell me more about it."}
            ]

            with patch('chat_logic.create_chat_history_reducer') as mock_reducer:
                mock_chat_history = Mock()
                mock_chat_history.messages = []
                mock_chat_history.target_count = 150000
                mock_chat_history.reduce = Mock()

                mock_chat_history.add_message = Mock()
                mock_reducer.return_value = mock_chat_history

                chat_history = await convert_firebase_messages_to_chat_history(firebase_messages)

                self.assertEqual(chat_history, mock_chat_history)
                self.assertEqual(mock_chat_history.add_message.call_count, 3)
                mock_reducer.assert_called_once()

        asyncio.run(run_test())

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
