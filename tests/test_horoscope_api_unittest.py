"""Comprehensive unit tests for horoscope functionality."""

import unittest
import asyncio
import json
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from models import (
    BirthData, CurrentLocation, GenerateHoroscopeRequest, GenerateHoroscopeResponse, 
    DailyTransitChange, TransitChanges, RetrogradeChanges,
    HoroscopePeriod, AstrologicalChart, PlanetPosition, HousePosition, SignData
)
from contexts import build_horoscope_context
from kerykeion.kr_types.kr_models import TransitsTimeRangeModel


class MockTransitMoment:
    """Mock class for transit moments."""
    
    def __init__(self, date_str, aspects=None):
        self.date = date_str
        self.aspects = aspects or []


class MockAspect:
    """Mock class for aspects."""
    
    def __init__(self, aspect_name="Conjunction", p1_name="Sun", p2_name="Moon", orbit=2.5, aspect_degrees=0):
        self.aspect = aspect_name
        self.p1_name = p1_name  
        self.p2_name = p2_name
        self.orbit = orbit
        self.aspect_degrees = aspect_degrees


class TestHoroscopeAPI(unittest.TestCase):
    """Test cases for horoscope API endpoint."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.birth_data = BirthData(
            birth_date="1990-06-15",
            birth_time="10:30",
            latitude=40.7128,
            longitude=-74.0060
        )
        
        self.current_location = CurrentLocation(
            latitude=40.7128,
            longitude=-74.0060
        )
        
        # Create mock transit changes
        self.transit_changes = DailyTransitChange(
            date="2024-06-15",
            aspects=TransitChanges(began=[], ended=[]),
            retrogrades=RetrogradeChanges(began=[], ended=[])
        )
        
        self.horoscope_request = GenerateHoroscopeRequest(
            birth_data=self.birth_data,
            transit_changes=self.transit_changes
        )
        
        # Create mock charts
        self.mock_charts = self._create_mock_charts()
        
        # Create mock transit data
        self.mock_transit_model = self._create_mock_transit_model()
    
    def _create_mock_charts(self):
        """Create mock astrological charts."""
        charts = []
        
        for i in range(7):  # 7 days for weekly horoscope
            planets = {
                "Sun": PlanetPosition(
                    name="Sun",
                    sign="Gemini",
                    house=10,
                    degree=25.0 + i,
                    retrograde=False
                ),
                "Moon": PlanetPosition(
                    name="Moon",
                    sign="Cancer",
                    house=11,
                    degree=15.0 + i * 2,
                    retrograde=False
                ),
                "Mercury": PlanetPosition(
                    name="Mercury",
                    sign="Gemini",
                    house=10,
                    degree=20.0 + i,
                    retrograde=i % 2 == 0  # Retrograde on even days
                )
            }
            
            houses = {
                "house_1": HousePosition(house=1, sign="Leo", degree=0.0),
                "house_10": HousePosition(house=10, sign="Gemini", degree=25.0)
            }
            
            sun_sign = SignData(name="Gemini", element="Air", modality="Mutable", ruling_planet="Mercury")
            moon_sign = SignData(name="Cancer", element="Water", modality="Cardinal", ruling_planet="Moon")
            ascendant = SignData(name="Leo", element="Fire", modality="Fixed", ruling_planet="Sun")
            
            chart = AstrologicalChart(
                planets=planets,
                houses=houses,
                sunSign=sun_sign,
                moonSign=moon_sign,
                ascendant=ascendant,
                chartSvg=f"<svg>chart day {i}</svg>",
                chartImageUrl=f"https://example.com/chart-{i}.svg"
            )
            charts.append(chart)
        
        return charts
    
    def _create_mock_transit_model(self):
        """Create mock TransitsTimeRangeModel."""
        mock_aspects = [
            MockAspect("Conjunction", "Sun", "Moon", 1.5, 0),
            MockAspect("Trine", "Venus", "Mars", 3.2, 120),
            MockAspect("Square", "Jupiter", "Saturn", 2.8, 90)
        ]
        
        mock_transits = []
        base_date = datetime(2024, 6, 15)
        
        for i in range(7):
            date_str = f"{base_date.year}-{base_date.month:02d}-{base_date.day + i:02d}"
            aspects_for_day = [mock_aspects[i % len(mock_aspects)]]
            mock_transits.append(MockTransitMoment(date_str, aspects_for_day))
        
        mock_model = Mock(spec=TransitsTimeRangeModel)
        mock_model.transits = mock_transits
        
        return mock_model
    
    def test_generate_horoscope_endpoint_success(self):
        """Test successful horoscope generation."""
        from routes import generate_horoscope
        
        with patch('routes.get_claude_client') as mock_get_claude:
            with patch('routes.generate_birth_chart') as mock_generate_birth_chart:
                with patch('routes.build_horoscope_context') as mock_build_context:
                    with patch('routes.call_claude_with_analytics') as mock_call_claude:
                        # Setup mocks
                        mock_birth_chart = Mock()
                        mock_generate_birth_chart.return_value = mock_birth_chart
                        mock_build_context.return_value = ("system prompt", "user context")
                    
                        # Mock call_claude_with_analytics response
                        from anthropic.types import TextBlock
                        mock_text_block = Mock(spec=TextBlock)
                        mock_text_block.text = "This week brings positive energy and new opportunities for growth in your career and relationships."
                        
                        mock_response = Mock()
                        mock_response.content = [mock_text_block]
                        mock_call_claude.return_value = mock_response
                    
                        # Test the endpoint
                        user = {'uid': 'test-user-123'}
                        result = asyncio.run(generate_horoscope(self.horoscope_request, user))
                        
                        # Verify the result
                        self.assertIsInstance(result, GenerateHoroscopeResponse)
                        self.assertIn("positive energy", result.horoscope_text)
                        self.assertEqual(result.target_date, "2024-06-15")
    
    def test_generate_horoscope_endpoint_invalid_json(self):
        """Test horoscope generation with invalid JSON response."""
        from routes import generate_horoscope
        
        with patch('routes.get_claude_client') as mock_get_claude:
            with patch('routes.generate_birth_chart') as mock_generate_birth_chart:
                with patch('routes.build_horoscope_context') as mock_build_context:
                    with patch('routes.call_claude_with_analytics') as mock_call_claude:
                        # Setup mocks
                        mock_birth_chart = Mock()
                        mock_generate_birth_chart.return_value = mock_birth_chart
                        mock_build_context.return_value = ("system prompt", "user context")
                        
                        # Mock call_claude_with_analytics response with invalid content
                        from anthropic.types import TextBlock
                        mock_text_block = Mock(spec=TextBlock)
                        mock_text_block.text = 'invalid response text'
                        
                        mock_response = Mock()
                        mock_response.content = [mock_text_block]
                        mock_call_claude.return_value = mock_response
                        
                        # Test the endpoint - it should return the text as-is
                        user = {'uid': 'test-user-123'}
                        result = asyncio.run(generate_horoscope(self.horoscope_request, user))
                        
                        # The endpoint just returns whatever Claude generates
                        self.assertIsInstance(result, GenerateHoroscopeResponse)
                        self.assertEqual(result.horoscope_text, 'invalid response text')
                        self.assertEqual(result.target_date, "2024-06-15")
    
    def test_generate_horoscope_endpoint_no_claude_client(self):
        """Test horoscope generation when Claude client is unavailable."""
        from routes import generate_horoscope
        
        with patch('routes.get_claude_client', return_value=None):
            user = {'uid': 'test-user-123'}
            
            from fastapi import HTTPException
            with self.assertRaises(HTTPException) as context:
                asyncio.run(generate_horoscope(self.horoscope_request, user))
            
            self.assertEqual(context.exception.status_code, 500)
            self.assertIn("Failed to generate horoscope", context.exception.detail)
    
    def test_generate_horoscope_endpoint_chart_generation_error(self):
        """Test horoscope generation when chart generation fails."""
        from routes import generate_horoscope
        
        with patch('routes.get_claude_client') as mock_get_claude:
            with patch('routes.generate_birth_chart') as mock_generate_birth_chart:
                # Setup mocks
                mock_get_claude.return_value = Mock()
                mock_generate_birth_chart.side_effect = Exception("Chart generation failed")
                
                user = {'uid': 'test-user-123'}
                
                from fastapi import HTTPException
                with self.assertRaises(HTTPException) as context:
                    asyncio.run(generate_horoscope(self.horoscope_request, user))
                
                self.assertEqual(context.exception.status_code, 500)
                self.assertIn("Failed to generate horoscope", context.exception.detail)
    


if __name__ == "__main__":
    unittest.main(verbosity=2)