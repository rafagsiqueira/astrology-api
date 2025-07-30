import pytest
import json
from unittest.mock import Mock, patch
from fastapi import HTTPException

from chat_logic import (
    validate_user_profile, build_astrological_context, build_chat_context,
    convert_firebase_messages_to_chat_history, create_streaming_response_data,
    create_error_response_data
)
from models import ChatMessage, CurrentLocation
from semantic_kernel.contents import AuthorRole


class TestChatBusinessLogic:
    """Test suite for chat business logic functions"""
    
    def test_validate_user_profile_valid(self):
        """Test profile validation with valid profile"""
        valid_profile = {
            'birth_date': '1990-01-01',
            'birth_time': '12:00',
            'latitude': 40.7128,
            'longitude': -74.0060,
            'timezone': 'America/New_York'
        }
        
        # Should not raise any exception
        validate_user_profile(valid_profile)
    
    def test_validate_user_profile_missing(self):
        """Test profile validation with missing profile"""
        with pytest.raises(HTTPException) as exc_info:
            validate_user_profile(None)
        
        assert exc_info.value.status_code == 400
        assert "User profile not found" in exc_info.value.detail
    
    def test_validate_user_profile_incomplete(self):
        """Test profile validation with incomplete profile"""
        incomplete_profile = {
            'birth_date': '1990-01-01',
            'birth_time': None,  # Missing
            'latitude': 40.7128,
            # longitude missing
            'timezone': 'America/New_York'
        }
        
        with pytest.raises(HTTPException) as exc_info:
            validate_user_profile(incomplete_profile)
        
        assert exc_info.value.status_code == 400
        assert "Profile is incomplete" in exc_info.value.detail
        assert "birth_time" in exc_info.value.detail
        assert "longitude" in exc_info.value.detail

    def test_build_chat_context_with_data(self):
        """Test chat context building with astrological data"""
        context_data = {
            "birth_chart": "Sun in Aquarius, Moon in Gemini...",
            "current_data": "Mars in Leo, Venus in Virgo..."
        }
        
        context = build_chat_context(context_data)
        
        assert "knowledgeable and friendly astrologer" in context
        assert "Birth Chart:" in context
        assert "Current Planetary Positions:" in context
        assert "JSON format" in context
        assert context_data["birth_chart"] in context
        assert context_data["current_data"] in context
    
    def test_build_chat_context_without_data(self):
        """Test chat context building without astrological data"""
        context = build_chat_context(None)
        
        assert "knowledgeable and friendly astrologer" in context
        assert "Birth Chart:" not in context
        assert "JSON format" in context

    @pytest.mark.asyncio
    async def test_convert_firebase_messages_to_chat_history(self):
        """Test conversion of Firebase messages to Semantic Kernel ChatHistory"""
        firebase_messages = [
            {"role": "user", "content": "What's my sign?"},
            {"role": "assistant", "content": "You're an Aquarius."},
            {"role": "user", "content": "Tell me more about it."}
        ]
        
        with patch('chat_logic.create_chat_history_reducer') as mock_reducer:
            # Mock the ChatHistorySummarizationReducer (which is a ChatHistory)
            mock_chat_history = Mock()
            mock_chat_history.messages = []
            mock_chat_history.target_count = 150000
            mock_chat_history.add_message = Mock(side_effect=lambda msg: mock_chat_history.messages.append(msg))
            mock_chat_history.reduce = Mock()
            
            # Set up messages after add_message calls
            def add_message_side_effect(msg):
                mock_msg = Mock()
                mock_msg.role = Mock()
                mock_msg.role.value = "user" if msg.role == AuthorRole.USER else "assistant"
                mock_msg.content = msg.content
                mock_chat_history.messages.append(mock_msg)
            
            mock_chat_history.add_message.side_effect = add_message_side_effect
            mock_reducer.return_value = mock_chat_history
            
            chat_history = await convert_firebase_messages_to_chat_history(firebase_messages)
            
            # Should have 3 messages
            assert len(chat_history.messages) == 3
            assert chat_history.messages[0].role.value == "user"
            assert chat_history.messages[0].content == "What's my sign?"
            assert chat_history.messages[1].role.value == "assistant"
            assert chat_history.messages[1].content == "You're an Aquarius."
            assert chat_history.messages[2].role.value == "user"
            assert chat_history.messages[2].content == "Tell me more about it."

    def test_create_streaming_response_data(self):
        """Test SSE data formatting for streaming response"""
        text_chunk = "Hello, this is a response chunk."
        
        result = create_streaming_response_data(text_chunk)
        
        assert result.startswith("data: ")
        assert result.endswith("\n\n")
        
        # Parse the JSON part
        json_part = result[6:-2]  # Remove "data: " and "\n\n"
        data = json.loads(json_part)
        assert data["type"] == "text_delta"
        assert data["data"]["delta"] == text_chunk
    
    def test_create_error_response_data(self):
        """Test SSE error data formatting"""
        error_message = "Something went wrong"
        
        result = create_error_response_data(error_message)
        
        assert result.startswith("data: ")
        assert result.endswith("\n\n")
        
        # Parse the JSON part
        json_part = result[6:-2]  # Remove "data: " and "\n\n"
        data = json.loads(json_part)
        assert data["type"] == "error"
        assert data["data"]["error"] == error_message
    
    @patch('chat_logic.generate_birth_chart')
    @patch('chat_logic.current_chart')
    def test_build_astrological_context(self, mock_current_chart, mock_birth_chart):
        """Test building astrological context from profile and location"""
        # Mock the chart objects
        mock_birth_chart_obj = Mock()
        mock_birth_chart_obj.to_string.return_value = "Birth chart data"
        mock_birth_chart.return_value = mock_birth_chart_obj
        
        mock_current_chart_obj = Mock()
        mock_current_chart_obj.to_string.return_value = "Current chart data"
        mock_current_chart.return_value = mock_current_chart_obj
        
        profile = {
            'birth_date': '1990-01-01',
            'birth_time': '12:00',
            'latitude': 40.7128,
            'longitude': -74.0060,
            'timezone': 'America/New_York'
        }
        current_location = CurrentLocation(latitude=40.7128, longitude=-74.0060)
        
        context_data, current_chart = build_astrological_context(profile, current_location)
        
        assert context_data["birth_chart"] == "Birth chart data"
        assert context_data["current_data"] == "Current chart data"
        assert current_chart == mock_current_chart_obj
        mock_birth_chart.assert_called_once()
        mock_current_chart.assert_called_once_with(current_location)