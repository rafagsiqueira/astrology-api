"""Core API routes tests - organized and comprehensive."""

import pytest
import unittest
import json
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from fastapi import HTTPException
from datetime import datetime

from main import app
from models import (
    BirthData, AnalysisRequest, ChatRequest, RelationshipAnalysisRequest,
    HoroscopeRequest, CompositeAnalysisRequest, DailyTransitRequest,
    DailyHoroscopeRequest, HoroscopePeriod, CurrentLocation
)


class TestAPICore(unittest.TestCase):
    """Test core API functionality."""
    
    def setUp(self):
        """Set up test client and fixtures."""
        self.client = TestClient(app)
        self.mock_user = {'uid': 'test-user-123', 'email': 'test@example.com'}
        
        self.birth_data = {
            "year": 1990,
            "month": 6,
            "day": 15,
            "hour": 10,
            "minute": 30,
            "city": "New York",
            "nation": "US",
            "latitude": 40.7128,
            "longitude": -74.0060,
            "timezone": "America/New_York"
        }
    
    def test_root_endpoint(self):
        """Test root endpoint returns proper response."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("message", data)
        self.assertIn("Cosmic Guru", data["message"])
    
    def test_health_check_endpoint(self):
        """Test health check endpoint."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status", data)
        self.assertEqual(data["status"], "healthy")


class TestChartGeneration(unittest.TestCase):
    """Test chart generation endpoints."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = TestClient(app)
        self.mock_user = {'uid': 'test-user-123'}
        
        self.birth_data_payload = {
            "year": 1990,
            "month": 6,
            "day": 15,
            "hour": 10,
            "minute": 30,
            "city": "New York", 
            "nation": "US",
            "latitude": 40.7128,
            "longitude": -74.0060,
            "timezone": "America/New_York"
        }
    
    @patch('routes.verify_firebase_token')
    @patch('routes.generate_birth_chart')
    def test_generate_chart_success(self, mock_generate, mock_verify):
        """Test successful chart generation."""
        mock_verify.return_value = self.mock_user
        mock_generate.return_value = Mock(
            planets={'sun': Mock()},
            houses={'1': Mock()},
            signs={'Leo': Mock()},
            svg_content='<svg>chart</svg>'
        )
        
        response = self.client.post(
            "/api/generate-chart",
            json=self.birth_data_payload,
            headers={"Authorization": "Bearer valid-token"}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("planets", data)
        self.assertIn("houses", data)
        self.assertIn("signs", data)
    
    @patch('routes.verify_firebase_token')
    def test_generate_chart_unauthorized(self, mock_verify):
        """Test chart generation without authorization."""
        mock_verify.side_effect = HTTPException(status_code=401, detail="Unauthorized")
        
        response = self.client.post(
            "/api/generate-chart",
            json=self.birth_data_payload,
            headers={"Authorization": "Bearer invalid-token"}
        )
        
        self.assertEqual(response.status_code, 401)
    
    @patch('routes.verify_firebase_token')
    @patch('routes.generate_birth_chart')
    def test_generate_chart_invalid_data(self, mock_generate, mock_verify):
        """Test chart generation with invalid birth data."""
        mock_verify.return_value = self.mock_user
        mock_generate.side_effect = Exception("Invalid birth data")
        
        invalid_data = self.birth_data_payload.copy()
        invalid_data['year'] = 0  # Invalid year
        
        response = self.client.post(
            "/api/generate-chart",
            json=invalid_data,
            headers={"Authorization": "Bearer valid-token"}
        )
        
        self.assertEqual(response.status_code, 500)


class TestPersonalityAnalysis(unittest.TestCase):
    """Test personality analysis endpoints."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = TestClient(app)
        self.mock_user = {'uid': 'test-user-123'}
        
        self.analysis_payload = {
            "chart": {
                "planets": {"sun": {"name": "Sun", "sign": "Gemini", "house": 3}},
                "houses": {"1": {"house": 1, "sign": "Aries"}},
                "signs": {"Gemini": {"name": "Gemini", "element": "Air"}},
                "svg_content": "<svg>chart</svg>"
            }
        }
    
    @patch('routes.verify_firebase_token')
    @patch('routes.get_claude_client')
    def test_analyze_personality_success(self, mock_claude, mock_verify):
        """Test successful personality analysis."""
        mock_verify.return_value = self.mock_user
        
        # Mock Claude response
        mock_response = Mock()
        mock_response.content = [Mock(text=json.dumps({
            "overview": "You are highly communicative...",
            "core_traits": ["Communicative", "Adaptable"],
            "strengths": ["Quick thinking"],
            "growth_areas": ["Focus"],
            "relationships": "You connect easily...",
            "career": "Ideal for communication roles..."
        }))]
        
        mock_claude_client = Mock()
        mock_claude_client.messages.create.return_value = mock_response
        mock_claude.return_value = mock_claude_client
        
        response = self.client.post(
            "/api/analyze-personality",
            json=self.analysis_payload,
            headers={"Authorization": "Bearer valid-token"}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("overview", data)
        self.assertIn("core_traits", data)


class TestRelationshipAnalysis(unittest.TestCase):
    """Test relationship analysis endpoints."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = TestClient(app)
        self.mock_user = {'uid': 'test-user-123'}
        
        self.relationship_payload = {
            "user_chart": {
                "planets": {"sun": {"name": "Sun", "sign": "Aries"}},
                "houses": {"1": {"house": 1, "sign": "Aries"}},
                "signs": {"Aries": {"name": "Aries", "element": "Fire"}},
                "svg_content": "<svg>user chart</svg>"
            },
            "partner_chart": {
                "planets": {"sun": {"name": "Sun", "sign": "Libra"}},
                "houses": {"1": {"house": 1, "sign": "Libra"}},
                "signs": {"Libra": {"name": "Libra", "element": "Air"}},
                "svg_content": "<svg>partner chart</svg>"
            }
        }
    
    @patch('routes.verify_firebase_token')
    @patch('routes.get_claude_client')
    def test_analyze_relationship_success(self, mock_claude, mock_verify):
        """Test successful relationship analysis."""
        mock_verify.return_value = self.mock_user
        
        # Mock Claude response
        mock_response = Mock()
        mock_response.content = [Mock(text=json.dumps({
            "overall_compatibility": 0.8,
            "summary": "This is a balanced partnership...",
            "strengths": ["Complementary energies"],
            "challenges": ["Different approaches"],
            "advice": "Focus on communication...",
            "long_term_potential": "High potential..."
        }))]
        
        mock_claude_client = Mock()
        mock_claude_client.messages.create.return_value = mock_response
        mock_claude.return_value = mock_claude_client
        
        response = self.client.post(
            "/api/analyze-relationship",
            json=self.relationship_payload,
            headers={"Authorization": "Bearer valid-token"}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("overall_compatibility", data)
        self.assertIn("summary", data)


class TestTransitEndpoints(unittest.TestCase):
    """Test transit-related endpoints."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = TestClient(app)
        self.mock_user = {'uid': 'test-user-123'}
        
        self.transit_payload = {
            "birth_data": {
                "year": 1990, "month": 6, "day": 15,
                "hour": 10, "minute": 30,
                "city": "New York", "nation": "US",
                "latitude": 40.7128, "longitude": -74.0060,
                "timezone": "America/New_York"
            },
            "current_location": {
                "latitude": 40.7128,
                "longitude": -74.0060,
                "timezone": "America/New_York"
            },
            "target_date": "2024-01-15T00:00:00",
            "period": "day"
        }
    
    @patch('routes.verify_firebase_token')
    @patch('routes.generate_transits')
    @patch('routes.diff_transits')
    def test_get_daily_transits_success(self, mock_diff, mock_generate, mock_verify):
        """Test successful daily transits generation."""
        mock_verify.return_value = self.mock_user
        
        # Mock transits
        mock_transit = Mock()
        mock_transit.date = datetime(2024, 1, 15)
        mock_transit.aspects = []
        mock_transit.retrograding = ["Mercury"]
        mock_generate.return_value = [mock_transit]
        
        # Mock diff transits
        mock_diff.return_value = {
            "2024-01-15": Mock(
                date="2024-01-15",
                aspects=Mock(began=[], ended=[]),
                retrogrades=Mock(began=["Mercury"], ended=[])
            )
        }
        
        response = self.client.post(
            "/api/get-daily-transits",
            json=self.transit_payload,
            headers={"Authorization": "Bearer valid-token"}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("transits", data)
        self.assertIn("changes", data)


class TestChatEndpoints(unittest.TestCase):
    """Test chat-related endpoints."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = TestClient(app)
        self.mock_user = {'uid': 'test-user-123'}
        
        self.chat_payload = {
            "message": "What does my Sun in Gemini mean?",
            "chart": {
                "planets": {"sun": {"name": "Sun", "sign": "Gemini"}},
                "houses": {},
                "signs": {},
                "svg_content": ""
            },
            "chat_history": []
        }
    
    @patch('routes.verify_firebase_token')
    @patch('routes.get_claude_client')
    def test_chat_endpoint_success(self, mock_claude, mock_verify):
        """Test successful chat interaction."""
        mock_verify.return_value = self.mock_user
        
        # Mock streaming response
        async def mock_stream():
            yield b'data: {"type": "content_block_delta", "delta": {"text": "Your Sun in Gemini"}}\n\n'
            yield b'data: {"type": "message_stop"}\n\n'
        
        mock_claude_client = Mock()
        mock_claude_client.messages.stream.return_value.__aenter__ = AsyncMock(return_value=mock_stream())
        mock_claude.return_value = mock_claude_client
        
        response = self.client.post(
            "/api/chat",
            json=self.chat_payload,
            headers={"Authorization": "Bearer valid-token"}
        )
        
        self.assertEqual(response.status_code, 200)


class TestErrorHandling(unittest.TestCase):
    """Test error handling across endpoints."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = TestClient(app)
    
    def test_invalid_json_payload(self):
        """Test handling of invalid JSON payloads."""
        response = self.client.post(
            "/api/generate-chart",
            content="invalid json",
            headers={"Content-Type": "application/json"}
        )
        
        self.assertEqual(response.status_code, 422)
    
    def test_missing_authorization_header(self):
        """Test handling of missing authorization headers."""
        response = self.client.post(
            "/api/generate-chart",
            json={"year": 1990}
        )
        
        self.assertEqual(response.status_code, 401)
    
    @patch('routes.verify_firebase_token')
    def test_service_unavailable_error(self, mock_verify):
        """Test handling of service unavailable errors."""
        mock_verify.side_effect = HTTPException(status_code=503, detail="Service unavailable")
        
        response = self.client.post(
            "/api/generate-chart",
            json={"year": 1990},
            headers={"Authorization": "Bearer token"}
        )
        
        self.assertEqual(response.status_code, 503)


if __name__ == '__main__':
    unittest.main()