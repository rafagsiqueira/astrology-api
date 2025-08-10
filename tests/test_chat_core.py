"""Core chat functionality tests - organized and comprehensive."""

import pytest
import unittest
import json
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime

from models import ChatMessage, AstrologicalChart

# Mock semantic kernel components since they might not be available
class MockAuthorRole:
    USER = "user"
    ASSISTANT = "assistant"

# Import what's available from chat_logic
try:
    from chat_logic import (
        validate_user_profile,
        load_chat_history_from_firebase,
        create_streaming_response_data,
        create_error_response_data,
        convert_firebase_messages_to_chat_history,
        create_chat_history_reducer
    )
    CHAT_LOGIC_AVAILABLE = True
except ImportError:
    CHAT_LOGIC_AVAILABLE = False


@unittest.skipUnless(CHAT_LOGIC_AVAILABLE, "chat_logic module not available")
class TestUserProfileValidation(unittest.TestCase):
    """Test user profile validation functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.complete_profile = {
            'uid': 'test-user-123',
            'birth_data': {
                'year': 1990, 'month': 6, 'day': 15,
                'city': 'New York', 'timezone': 'America/New_York'
            },
            'astrology_chart': {
                'planets': {'sun': {'sign': 'Gemini'}},
                'houses': {'1': {'sign': 'Gemini'}},
                'signs': {'Gemini': {'element': 'Air'}}
            }
        }
        
        self.incomplete_profile = {
            'uid': 'test-user-456'
        }
    
    def test_validate_user_profile_complete(self):
        """Test validation with complete profile."""
        result = validate_user_profile(self.complete_profile)
        self.assertTrue(result)
    
    def test_validate_user_profile_missing_birth_data(self):
        """Test validation with missing birth data."""
        profile = self.complete_profile.copy()
        del profile['birth_data']
        
        result = validate_user_profile(profile)
        self.assertFalse(result)
    
    def test_validate_user_profile_missing_chart(self):
        """Test validation with missing astrology chart."""
        profile = self.complete_profile.copy()
        del profile['astrology_chart']
        
        result = validate_user_profile(profile)
        self.assertFalse(result)
    
    def test_validate_user_profile_empty_profile(self):
        """Test validation with empty profile."""
        result = validate_user_profile({})
        self.assertFalse(result)
    
    def test_validate_user_profile_none(self):
        """Test validation with None profile."""
        result = validate_user_profile(None)
        self.assertFalse(result)


@unittest.skipUnless(CHAT_LOGIC_AVAILABLE, "chat_logic module not available")
class TestChatHistoryHandling(unittest.TestCase):
    """Test chat history loading and conversion."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_firebase_messages = [
            {
                'role': 'user',
                'content': 'What does my Sun in Gemini mean?',
                'timestamp': datetime(2024, 1, 15, 10, 0).isoformat()
            },
            {
                'role': 'assistant',
                'content': 'Your Sun in Gemini indicates strong communication skills...',
                'timestamp': datetime(2024, 1, 15, 10, 1).isoformat()
            },
            {
                'role': 'user',
                'content': 'Tell me about my Moon sign too.',
                'timestamp': datetime(2024, 1, 15, 10, 5).isoformat()
            }
        ]
    
    @patch('chat_logic.get_firestore_client')
    def test_load_chat_history_from_firebase_success(self, mock_get_client):
        """Test successful chat history loading."""
        # Mock Firestore client and collection
        mock_db = Mock()
        mock_collection = Mock()
        mock_query = Mock()
        mock_docs = [
            Mock(to_dict=lambda: msg) for msg in self.mock_firebase_messages
        ]
        
        mock_query.stream.return_value = mock_docs
        mock_collection.order_by.return_value = mock_query
        mock_db.collection.return_value = mock_collection
        mock_get_client.return_value = mock_db
        
        result = load_chat_history_from_firebase('test-user-123')
        
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]['role'], 'user')
        self.assertEqual(result[1]['role'], 'assistant')
    
    @patch('chat_logic.get_firestore_client')
    def test_load_chat_history_from_firebase_error(self, mock_get_client):
        """Test chat history loading with Firestore error."""
        mock_get_client.side_effect = Exception("Firestore error")
        
        result = load_chat_history_from_firebase('test-user-123')
        
        self.assertEqual(result, [])  # Should return empty list on error
    
    def test_convert_firebase_messages_to_chat_history(self):
        """Test conversion of Firebase messages to chat history format."""
        import asyncio
        result = asyncio.run(convert_firebase_messages_to_chat_history(self.mock_firebase_messages))
        
        self.assertEqual(len(result), 3)
        
        # Check first message (user)
        self.assertEqual(result[0].role, MockAuthorRole.USER)
        self.assertEqual(result[0].content, 'What does my Sun in Gemini mean?')
        
        # Check second message (assistant)
        self.assertEqual(result[1].role, MockAuthorRole.ASSISTANT)
        self.assertIn('communication skills', result[1].content)
        
        # Check third message (user)
        self.assertEqual(result[2].role, MockAuthorRole.USER)
        self.assertIn('Moon sign', result[2].content)
    
    def test_convert_firebase_messages_empty_list(self):
        """Test conversion with empty message list."""
        result = convert_firebase_messages_to_chat_history([])
        self.assertEqual(result, [])
    
    def test_convert_firebase_messages_unknown_role(self):
        """Test conversion with unknown role."""
        messages = [
            {
                'role': 'unknown_role',
                'content': 'Test message',
                'timestamp': datetime.now().isoformat()
            }
        ]
        
        result = convert_firebase_messages_to_chat_history(messages)
        
        # Should default to USER role for unknown roles
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].role, MockAuthorRole.USER)


@unittest.skipUnless(CHAT_LOGIC_AVAILABLE, "chat_logic module not available")
class TestStreamingResponseHandling(unittest.TestCase):
    """Test streaming response creation and handling."""
    
    def test_create_streaming_response_data_content_delta(self):
        """Test creating streaming response for content delta."""
        chunk_data = {
            'type': 'content_block_delta',
            'delta': {'text': 'Your Sun in Gemini '}
        }
        
        result = create_streaming_response_data(chunk_data)
        expected = 'data: {"type": "content_block_delta", "delta": {"text": "Your Sun in Gemini "}}\n\n'
        
        self.assertEqual(result, expected)
    
    def test_create_streaming_response_data_message_stop(self):
        """Test creating streaming response for message stop."""
        chunk_data = {'type': 'message_stop'}
        
        result = create_streaming_response_data(chunk_data)
        expected = 'data: {"type": "message_stop"}\n\n'
        
        self.assertEqual(result, expected)
    
    def test_create_streaming_response_data_with_special_characters(self):
        """Test streaming response with special characters."""
        chunk_data = {
            'type': 'content_block_delta',
            'delta': {'text': 'Your chart shows "growth" & change...'}
        }
        
        result = create_streaming_response_data(chunk_data)
        
        self.assertIn('growth', result)
        self.assertIn('&', result)
        self.assertTrue(result.startswith('data:'))
        self.assertTrue(result.endswith('\n\n'))
    
    def test_create_error_response_data(self):
        """Test creating error response data."""
        error_message = "Failed to analyze chart"
        
        result = create_error_response_data(error_message)
        expected = 'data: {"type": "error", "message": "Failed to analyze chart"}\n\n'
        
        self.assertEqual(result, expected)
    
    def test_create_error_response_data_with_quotes(self):
        """Test error response with quotes in message."""
        error_message = 'Chart analysis failed: "Invalid data" provided'
        
        result = create_error_response_data(error_message)
        
        self.assertIn('Invalid data', result)
        self.assertTrue(result.startswith('data:'))
        self.assertIn('"type": "error"', result)


@unittest.skipUnless(CHAT_LOGIC_AVAILABLE, "chat_logic module not available")
class TestChatHistoryReducer(unittest.TestCase):
    """Test chat history reduction functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.long_chat_history = []
        for i in range(20):  # Create 20 messages
            self.long_chat_history.append(ChatMessage(
                role='user' if i % 2 == 0 else 'assistant',
                content=f'Message {i + 1}',
                timestamp=datetime(2024, 1, 15, 10, i).isoformat()
            ))
    
    def test_create_chat_history_reducer_basic(self):
        """Test basic chat history reducer functionality."""
        reducer = create_chat_history_reducer(max_messages=10)
        
        self.assertIsCallable(reducer)
    
    def test_chat_history_reducer_under_limit(self):
        """Test reducer with chat history under the limit."""
        reducer = create_chat_history_reducer(max_messages=25)
        
        result = reducer(self.long_chat_history)
        
        self.assertEqual(len(result), 20)  # All messages preserved
        self.assertEqual(result[0].content, 'Message 1')
        self.assertEqual(result[-1].content, 'Message 20')
    
    def test_chat_history_reducer_over_limit(self):
        """Test reducer with chat history over the limit."""
        reducer = create_chat_history_reducer(max_messages=10)
        
        result = reducer(self.long_chat_history)
        
        self.assertEqual(len(result), 10)  # Reduced to limit
        # Should keep the most recent messages
        self.assertEqual(result[0].content, 'Message 11')
        self.assertEqual(result[-1].content, 'Message 20')
    
    def test_chat_history_reducer_preserve_context(self):
        """Test that reducer preserves conversation context."""
        reducer = create_chat_history_reducer(max_messages=6)
        
        result = reducer(self.long_chat_history)
        
        self.assertEqual(len(result), 6)
        # Should alternate between user and assistant
        for i, message in enumerate(result):
            expected_role = 'user' if (14 + i) % 2 == 0 else 'assistant'
            self.assertEqual(message.role, expected_role)
    
    def test_chat_history_reducer_empty_history(self):
        """Test reducer with empty chat history."""
        reducer = create_chat_history_reducer(max_messages=10)
        
        result = reducer([])
        
        self.assertEqual(result, [])


@unittest.skipUnless(CHAT_LOGIC_AVAILABLE, "chat_logic module not available")
class TestChatLogicIntegration(unittest.TestCase):
    """Test integration between different chat logic components."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.user_profile = {
            'uid': 'test-user-123',
            'birth_data': {'year': 1990, 'month': 6},
            'astrology_chart': {
                'planets': {'sun': {'sign': 'Gemini'}},
                'houses': {},
                'signs': {}
            }
        }
    
    @patch('chat_logic.load_chat_history_from_firebase')
    def test_chat_pipeline_integration(self, mock_load_history):
        """Test integration of chat components."""
        # Mock chat history
        mock_load_history.return_value = [
            {
                'role': 'user',
                'content': 'Previous question',
                'timestamp': datetime.now().isoformat()
            }
        ]
        
        # Test profile validation
        is_valid = validate_user_profile(self.user_profile)
        self.assertTrue(is_valid)
        
        # Test history loading
        history = load_chat_history_from_firebase('test-user-123')
        self.assertEqual(len(history), 1)
        
        # Test history conversion
        chat_history = convert_firebase_messages_to_chat_history(history)
        self.assertEqual(len(chat_history), 1)
        self.assertEqual(chat_history[0].role, MockAuthorRole.USER)
    
    def test_error_handling_pipeline(self):
        """Test error handling across chat pipeline."""
        # Test with invalid profile
        is_valid = validate_user_profile({})
        self.assertFalse(is_valid)
        
        # Test error response creation
        error_response = create_error_response_data("Profile incomplete")
        self.assertIn("error", error_response)
        self.assertIn("Profile incomplete", error_response)


@unittest.skipUnless(CHAT_LOGIC_AVAILABLE, "chat_logic module not available")
class TestChatMessageFormatting(unittest.TestCase):
    """Test chat message formatting and validation."""
    
    def test_chat_message_creation(self):
        """Test ChatMessage model creation."""
        message = ChatMessage(
            role='user',
            content='What does my chart mean?',
            timestamp=datetime.now().isoformat()
        )
        
        self.assertEqual(message.role, 'user')
        self.assertEqual(message.content, 'What does my chart mean?')
        self.assertIsNotNone(message.timestamp)
    
    def test_chat_message_validation(self):
        """Test ChatMessage validation."""
        # Valid message
        valid_message = ChatMessage(
            role='assistant',
            content='Your chart shows...',
            timestamp=datetime.now().isoformat()
        )
        
        self.assertIsInstance(valid_message.role, str)
        self.assertIsInstance(valid_message.content, str)
        self.assertIsInstance(valid_message.timestamp, str)


if __name__ == '__main__':
    unittest.main()