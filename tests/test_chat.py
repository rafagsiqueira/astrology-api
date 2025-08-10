import pytest
import json
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
        
        assert "knowledgeable and friendly cosmicloger" in context
        assert "Birth Chart:" in context
        assert "Current Planetary Positions:" in context
        assert "JSON format" in context
        assert context_data["birth_chart"] in context
        assert context_data["current_data"] in context
    
    def test_build_chat_context_without_data(self):
        """Test chat context building without astrological data"""
        context = build_chat_context(None)
        
        assert "knowledgeable and friendly cosmicloger" in context
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
            mock_chat_history.reduce = Mock()
            
            # Simple mock that just tracks call count
            mock_chat_history.add_message = Mock()
            mock_reducer.return_value = mock_chat_history
            
            chat_history = await convert_firebase_messages_to_chat_history(firebase_messages)
            
            # Verify the function was called and add_message was invoked 3 times
            assert chat_history == mock_chat_history
            assert mock_chat_history.add_message.call_count == 3
            
            # Verify the chat history reducer was created once
            mock_reducer.assert_called_once()

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
    
    def test_build_astrological_context(self):
        """Test building astrological context from profile and location"""
        profile = {
            'birth_date': '1990-01-01',
            'birth_time': '12:00',
            'latitude': 40.7128,
            'longitude': -74.0060,
            'timezone': 'America/New_York'
        }
        current_location = CurrentLocation(latitude=40.7128, longitude=-74.0060)
        
        context_data, current_chart = build_astrological_context(profile, current_location)
        
        # Verify the structure of returned data
        assert isinstance(context_data, dict)
        assert "birth_chart" in context_data
        assert "current_data" in context_data
        assert isinstance(context_data["birth_chart"], str)
        assert isinstance(context_data["current_data"], list)  # transit_aspects is a list
        assert len(context_data["birth_chart"]) > 0
        assert len(context_data["current_data"]) >= 0  # could be empty list
        
        # Verify the current_chart is returned (it's the same as current_data)
        assert current_chart == context_data["current_data"]