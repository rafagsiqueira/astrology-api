"""Comprehensive unit tests for horoscope functionality."""

import unittest
import asyncio
import json
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from models import (
    BirthData, CurrentLocation, HoroscopeRequest, HoroscopeResponse, 
    HoroscopePeriod, CosmiclogicalChart, PlanetPosition, HousePosition, SignData
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
        
        self.horoscope_request = HoroscopeRequest(
            birth_data=self.birth_data,
            current_location=self.current_location,
            horoscope_type=HoroscopePeriod.WEEK
        )
        
        # Create mock charts
        self.mock_charts = self._create_mock_charts()
        
        # Create mock transit data
        self.mock_transit_model = self._create_mock_transit_model()
    
    def _create_mock_charts(self):
        """Create mock cosmiclogical charts."""
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
            
            chart = CosmiclogicalChart(
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
            with patch('routes.generate_transits') as mock_generate_transits:
                with patch('routes.build_horoscope_context') as mock_build_context:
                    # Setup mocks
                    mock_generate_transits.return_value = (self.mock_transit_model, self.mock_charts)
                    mock_build_context.return_value = ("system prompt", "user context")
                    
                    # Mock Claude client response
                    from anthropic.types import TextBlock
                    mock_text_block = Mock(spec=TextBlock)
                    mock_text_block.text = '''
"overvall_summary": "This week brings positive energy and new opportunities for growth.",
"specific_findings": [
    {
        "date": "2024-06-15", 
        "horoscope": "A day of new beginnings with the Sun-Moon conjunction.",
        "active_aspects": ["Sun conjunction Moon"],
        "retrograding_planets": ["Mercury"]
    },
    {
        "date": "2024-06-16",
        "horoscope": "Creative energy flows with Venus trine Mars.",
        "active_aspects": ["Venus trine Mars"],
        "retrograding_planets": []
    }
]
}'''
                    
                    mock_usage = Mock()
                    mock_usage.input_tokens = 500
                    mock_usage.output_tokens = 200
                    
                    mock_response = Mock()
                    mock_response.content = [mock_text_block]
                    mock_response.usage = mock_usage
                    
                    mock_claude = Mock()
                    mock_claude.messages.create.return_value = mock_response
                    mock_get_claude.return_value = mock_claude
                    
                    # Test the endpoint
                    user = {'uid': 'test-user-123'}
                    result = asyncio.run(generate_horoscope(self.horoscope_request, user))
                    
                    # Verify the result
                    self.assertIsInstance(result, HoroscopeResponse)
                    self.assertIn("positive energy", result.overall_summary)
                    self.assertIn("new opportunities", result.overall_summary)
                    self.assertEqual(len(result.specific_findings), 2)
                    self.assertEqual(len(result.chart_urls), 7)  # 7 charts for week
    
    def test_generate_horoscope_endpoint_invalid_json(self):
        """Test horoscope generation with invalid JSON response."""
        from routes import generate_horoscope
        
        with patch('routes.get_claude_client') as mock_get_claude:
            with patch('routes.generate_transits') as mock_generate_transits:
                with patch('routes.build_horoscope_context') as mock_build_context:
                    # Setup mocks
                    mock_generate_transits.return_value = (self.mock_transit_model, self.mock_charts)
                    mock_build_context.return_value = ("system prompt", "user context")
                    
                    # Mock Claude client response with invalid JSON
                    from anthropic.types import TextBlock
                    mock_text_block = Mock(spec=TextBlock)
                    mock_text_block.text = 'invalid json response'
                    
                    mock_usage = Mock()
                    mock_usage.input_tokens = 500
                    mock_usage.output_tokens = 50
                    
                    mock_response = Mock()
                    mock_response.content = [mock_text_block]
                    mock_response.usage = mock_usage
                    
                    mock_claude = Mock()
                    mock_claude.messages.create.return_value = mock_response
                    mock_get_claude.return_value = mock_claude
                    
                    # Test should raise HTTPException
                    user = {'uid': 'test-user-123'}
                    
                    from fastapi import HTTPException
                    with self.assertRaises(HTTPException) as context:
                        asyncio.run(generate_horoscope(self.horoscope_request, user))
                    
                    self.assertEqual(context.exception.status_code, 500)
                    self.assertIn("Failed to generate horoscope", context.exception.detail)
    
    def test_generate_horoscope_endpoint_no_claude_client(self):
        """Test horoscope generation when Claude client is unavailable."""
        from routes import generate_horoscope
        
        with patch('routes.get_claude_client', return_value=None):
            user = {'uid': 'test-user-123'}
            
            from fastapi import HTTPException
            with self.assertRaises(HTTPException) as context:
                asyncio.run(generate_horoscope(self.horoscope_request, user))
            
            self.assertEqual(context.exception.status_code, 503)
            self.assertIn("Horoscope service not available", context.exception.detail)
    
    def test_generate_horoscope_endpoint_transit_generation_error(self):
        """Test horoscope generation when transit generation fails."""
        from routes import generate_horoscope
        
        with patch('routes.get_claude_client') as mock_get_claude:
            with patch('routes.generate_transits') as mock_generate_transits:
                # Setup mocks
                mock_get_claude.return_value = Mock()
                mock_generate_transits.side_effect = Exception("Transit generation failed")
                
                user = {'uid': 'test-user-123'}
                
                from fastapi import HTTPException
                with self.assertRaises(HTTPException) as context:
                    asyncio.run(generate_horoscope(self.horoscope_request, user))
                
                self.assertEqual(context.exception.status_code, 500)
                self.assertIn("Failed to generate horoscope", context.exception.detail)
    
    def test_horoscope_context_building_with_retrograde_planets(self):
        """Test that horoscope context correctly includes retrograde planets."""
        context_system, context_user = build_horoscope_context(
            self.mock_transit_model,
            self.mock_charts,
            HoroscopePeriod.WEEK
        )
        
        # Check system context
        self.assertIn("astrology guru", context_system)
        self.assertIn("JSON", context_system)
        self.assertIn("overall_summary", context_system)
        self.assertIn("specific_findings", context_system)
        
        # Check user context includes aspects and retrograde information
        self.assertIn("cosmiclogical aspects", context_user)
        self.assertIn("WEEK", context_user)
        
        # Parse the transits data from context to verify structure
        import re
        aspects_match = re.search(r'<aspects>(.*?)</aspects>', context_user, re.DOTALL)
        self.assertIsNotNone(aspects_match)
    
    def test_horoscope_context_with_different_periods(self):
        """Test horoscope context generation for different time periods."""
        periods = [HoroscopePeriod.WEEK, HoroscopePeriod.MONTH, HoroscopePeriod.YEAR]
        
        for period in periods:
            with self.subTest(period=period):
                system, user = build_horoscope_context(
                    self.mock_transit_model,
                    self.mock_charts,
                    period
                )
                
                # Check that the period is correctly included in user context
                self.assertIn(period.value.upper(), user)
                
                # Check basic structure
                self.assertIn("astrology guru", system)
                self.assertIn("JSON", system)
                self.assertIn("aspects", user)
    
    def test_horoscope_context_with_empty_charts(self):
        """Test horoscope context generation with empty charts list."""
        system, user = build_horoscope_context(
            self.mock_transit_model,
            [],  # Empty charts list
            HoroscopePeriod.WEEK
        )
        
        # Should still generate valid context
        self.assertIsInstance(system, str)
        self.assertIsInstance(user, str)
        self.assertGreater(len(system), 500)
        self.assertGreater(len(user), 50)
        
        # Should still contain basic structure
        self.assertIn("astrology guru", system)
        self.assertIn("aspects", user)
    
    def test_horoscope_context_aspect_formatting(self):
        """Test that aspects are properly formatted in the context."""
        system, user = build_horoscope_context(
            self.mock_transit_model,
            self.mock_charts,
            HoroscopePeriod.WEEK
        )
        
        # Check for proper aspect formatting in the generated context
        # The transits should be formatted as a list with date, aspects, and retrograde planets
        self.assertIn("2024-06-15", user)  # Should include dates from mock data
        self.assertIn("aspects", user)
        self.assertIn("retrograding_planets", user)
    
    def test_monthly_horoscope_generation(self):
        """Test monthly horoscope generation specifically."""
        monthly_request = HoroscopeRequest(
            birth_data=self.birth_data,
            current_location=self.current_location,
            horoscope_type=HoroscopePeriod.MONTH
        )
        
        from routes import generate_horoscope
        
        with patch('routes.get_claude_client') as mock_get_claude:
            with patch('routes.generate_transits') as mock_generate_transits:
                with patch('routes.build_horoscope_context') as mock_build_context:
                    # Setup mocks for monthly charts (30 charts)
                    monthly_charts = self.mock_charts * 5  # Simulate 30+ charts
                    mock_generate_transits.return_value = (self.mock_transit_model, monthly_charts)
                    mock_build_context.return_value = ("system prompt for MONTH", "user context for MONTH")
                    
                    # Mock Claude response
                    from anthropic.types import TextBlock
                    mock_text_block = Mock(spec=TextBlock)
                    mock_text_block.text = '''
"overvall_summary": "This month focuses on career growth and relationship harmony.",
"specific_findings": [
    {
        "date": "2024-06-15",
        "horoscope": "Focus on career opportunities this week.",
        "active_aspects": ["Sun trine Jupiter"],
        "retrograding_planets": ["Mercury"]
    }
]
}'''
                    
                    mock_usage = Mock()
                    mock_usage.input_tokens = 800
                    mock_usage.output_tokens = 300
                    
                    mock_response = Mock()
                    mock_response.content = [mock_text_block]
                    mock_response.usage = mock_usage
                    
                    mock_claude = Mock()
                    mock_claude.messages.create.return_value = mock_response
                    mock_get_claude.return_value = mock_claude
                    
                    # Test the endpoint
                    user = {'uid': 'test-user-123'}
                    result = asyncio.run(generate_horoscope(monthly_request, user))
                    
                    # Verify monthly-specific results
                    self.assertIsInstance(result, HoroscopeResponse)
                    self.assertIn("career growth", result.overall_summary)
                    self.assertIn("relationship harmony", result.overall_summary)
                    self.assertEqual(len(result.chart_urls), len(monthly_charts))
                    
                    # Verify that monthly context was used
                    mock_build_context.assert_called_once_with(
                        self.mock_transit_model, 
                        monthly_charts, 
                        HoroscopePeriod.MONTH
                    )
    
    def test_yearly_horoscope_generation(self):
        """Test yearly horoscope generation specifically."""
        yearly_request = HoroscopeRequest(
            birth_data=self.birth_data,
            current_location=self.current_location,
            horoscope_type=HoroscopePeriod.YEAR
        )
        
        from routes import generate_horoscope
        
        with patch('routes.get_claude_client') as mock_get_claude:
            with patch('routes.generate_transits') as mock_generate_transits:
                with patch('routes.build_horoscope_context') as mock_build_context:
                    # Setup mocks for yearly charts (12 monthly charts)
                    yearly_charts = [self.mock_charts[i % 7] for i in range(12)]  # 12 charts for year
                    mock_generate_transits.return_value = (self.mock_transit_model, yearly_charts)
                    mock_build_context.return_value = ("system prompt for YEAR", "user context for YEAR")
                    
                    # Mock Claude response
                    from anthropic.types import TextBlock
                    mock_text_block = Mock(spec=TextBlock)
                    mock_text_block.text = '''
"overvall_summary": "This year brings transformation and spiritual growth across all areas of life.",
"specific_findings": [
    {
        "date": "2024-06-15",
        "horoscope": "Summer brings opportunities for personal transformation.",
        "active_aspects": ["Pluto square Sun"],
        "retrograding_planets": ["Mercury", "Venus"]
    }
]
}'''
                    
                    mock_usage = Mock()
                    mock_usage.input_tokens = 1200
                    mock_usage.output_tokens = 400
                    
                    mock_response = Mock()
                    mock_response.content = [mock_text_block]
                    mock_response.usage = mock_usage
                    
                    mock_claude = Mock()
                    mock_claude.messages.create.return_value = mock_response
                    mock_get_claude.return_value = mock_claude
                    
                    # Test the endpoint
                    user = {'uid': 'test-user-123'}
                    result = asyncio.run(generate_horoscope(yearly_request, user))
                    
                    # Verify yearly-specific results
                    self.assertIsInstance(result, HoroscopeResponse)
                    self.assertIn("transformation", result.overall_summary)
                    self.assertIn("spiritual growth", result.overall_summary)
                    self.assertEqual(len(result.chart_urls), 12)
                    
                    # Verify that yearly context was used
                    mock_build_context.assert_called_once_with(
                        self.mock_transit_model, 
                        yearly_charts, 
                        HoroscopePeriod.YEAR
                    )


if __name__ == "__main__":
    unittest.main(verbosity=2)