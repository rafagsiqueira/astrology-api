"""Integration tests for horoscope functionality - testing the full pipeline."""

import unittest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
from models import (
    BirthData, CurrentLocation, HoroscopeRequest, HoroscopeResponse, 
    HoroscopePeriod
)


class TestHoroscopeIntegration(unittest.TestCase):
    """Integration tests for the complete horoscope generation pipeline."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_birth_data = BirthData(
            birth_date="1990-06-15",
            birth_time="14:30",
            latitude=37.7749,  # San Francisco
            longitude=-122.4194
        )
        
        self.test_location = CurrentLocation(
            latitude=37.7749,
            longitude=-122.4194
        )
    
    def test_full_horoscope_pipeline_weekly(self):
        """Test the complete pipeline for weekly horoscope generation."""
        from routes import generate_horoscope
        
        request = HoroscopeRequest(
            birth_data=self.test_birth_data,
            current_location=self.test_location,
            horoscope_type=HoroscopePeriod.WEEK
        )
        
        # Mock all external dependencies but test the actual business logic flow
        with patch('routes.get_claude_client') as mock_get_claude:
            with patch('routes.generate_transits') as mock_generate_transits:
                with patch('routes.call_claude_with_analytics') as mock_call_claude:
                    
                    # Setup realistic mock responses
                    mock_transits = self._create_realistic_transits_response()
                    mock_charts = self._create_realistic_charts_response(7)  # 7 days
                    mock_generate_transits.return_value = (mock_transits, mock_charts)
                    
                    # Mock Claude API response
                    mock_claude_response = self._create_realistic_claude_response("weekly")
                    mock_call_claude.return_value = mock_claude_response
                    
                    # Mock Claude client
                    mock_get_claude.return_value = Mock()
                    
                    # Execute the full pipeline
                    user = {'uid': 'integration-test-user'}
                    result = asyncio.run(generate_horoscope(request, user))
                    
                    # Verify the complete flow
                    self.assertIsInstance(result, HoroscopeResponse)
                    self.assertIn("week", result.overall_summary.lower())
                    self.assertGreater(len(result.specific_findings), 0)
                    self.assertEqual(len(result.chart_urls), 7)
                    
                    # Verify that the transit generation was called correctly
                    mock_generate_transits.assert_called_once_with(
                        self.test_birth_data, 
                        self.test_location, 
                        HoroscopePeriod.WEEK
                    )
                    
                    # Verify that Claude was called with proper parameters
                    mock_call_claude.assert_called_once()
                    call_args = mock_call_claude.call_args
                    self.assertEqual(call_args.kwargs['endpoint_name'], 'generate-horoscope')
                    self.assertEqual(call_args.kwargs['user_id'], 'integration-test-user')
                    self.assertEqual(call_args.kwargs['model'], 'claude-3-5-haiku-latest')
                    self.assertEqual(call_args.kwargs['max_tokens'], 1500)
    
    def test_full_horoscope_pipeline_monthly(self):
        """Test the complete pipeline for monthly horoscope generation."""
        from routes import generate_horoscope
        
        request = HoroscopeRequest(
            birth_data=self.test_birth_data,
            current_location=self.test_location,
            horoscope_type=HoroscopePeriod.MONTH
        )
        
        with patch('routes.get_claude_client') as mock_get_claude:
            with patch('routes.generate_transits') as mock_generate_transits:
                with patch('routes.call_claude_with_analytics') as mock_call_claude:
                    
                    # Setup monthly mock responses
                    mock_transits = self._create_realistic_transits_response(30)  # 30 days
                    mock_charts = self._create_realistic_charts_response(30)
                    mock_generate_transits.return_value = (mock_transits, mock_charts)
                    
                    mock_claude_response = self._create_realistic_claude_response("monthly")
                    mock_call_claude.return_value = mock_claude_response
                    
                    mock_get_claude.return_value = Mock()
                    
                    # Execute the pipeline
                    user = {'uid': 'integration-test-user'}
                    result = asyncio.run(generate_horoscope(request, user))
                    
                    # Verify monthly-specific results
                    self.assertIsInstance(result, HoroscopeResponse)
                    self.assertIn("month", result.overall_summary.lower())
                    self.assertEqual(len(result.chart_urls), 30)
                    
                    # Verify monthly context was used
                    mock_generate_transits.assert_called_once_with(
                        self.test_birth_data, 
                        self.test_location, 
                        HoroscopePeriod.MONTH
                    )
    
    def test_full_horoscope_pipeline_yearly(self):
        """Test the complete pipeline for yearly horoscope generation."""
        from routes import generate_horoscope
        
        request = HoroscopeRequest(
            birth_data=self.test_birth_data,
            current_location=self.test_location,
            horoscope_type=HoroscopePeriod.YEAR
        )
        
        with patch('routes.get_claude_client') as mock_get_claude:
            with patch('routes.generate_transits') as mock_generate_transits:
                with patch('routes.call_claude_with_analytics') as mock_call_claude:
                    
                    # Setup yearly mock responses (12 months)
                    mock_transits = self._create_realistic_transits_response(12)
                    mock_charts = self._create_realistic_charts_response(12)
                    mock_generate_transits.return_value = (mock_transits, mock_charts)
                    
                    mock_claude_response = self._create_realistic_claude_response("yearly")
                    mock_call_claude.return_value = mock_claude_response
                    
                    mock_get_claude.return_value = Mock()
                    
                    # Execute the pipeline
                    user = {'uid': 'integration-test-user'}
                    result = asyncio.run(generate_horoscope(request, user))
                    
                    # Verify yearly-specific results
                    self.assertIsInstance(result, HoroscopeResponse)
                    self.assertIn("year", result.overall_summary.lower())
                    self.assertEqual(len(result.chart_urls), 12)
                    
                    # Verify yearly context was used
                    mock_generate_transits.assert_called_once_with(
                        self.test_birth_data, 
                        self.test_location, 
                        HoroscopePeriod.YEAR
                    )
    
    def test_horoscope_context_integration_with_real_data_structure(self):
        """Test that the context building integrates properly with realistic data structures."""
        from contexts import build_horoscope_context
        
        # Create realistic mock data that matches what generate_transits would return
        realistic_transits = self._create_realistic_transits_response()
        realistic_charts = self._create_realistic_charts_response(7)
        
        # Test all horoscope periods
        for period in [HoroscopePeriod.WEEK, HoroscopePeriod.MONTH, HoroscopePeriod.YEAR]:
            with self.subTest(period=period):
                system, user = build_horoscope_context(realistic_transits, realistic_charts, period)
                
                # Verify context structure
                self.assertIsInstance(system, str)
                self.assertIsInstance(user, str)
                self.assertGreater(len(system), 1000)
                self.assertGreater(len(user), 100)
                
                # Verify period-specific content in user context
                self.assertIn(period.value.upper(), user)
                self.assertIn("astrology guru", system)
                self.assertIn("JSON", system)
                
                # Verify realistic data is included
                self.assertIn("aspects", user)
                self.assertIn("2025-", user)  # Should contain realistic dates
    
    def test_error_handling_in_pipeline(self):
        """Test error handling throughout the horoscope generation pipeline."""
        from routes import generate_horoscope
        from fastapi import HTTPException
        
        request = HoroscopeRequest(
            birth_data=self.test_birth_data,
            current_location=self.test_location,
            horoscope_type=HoroscopePeriod.WEEK
        )
        
        user = {'uid': 'error-test-user'}
        
        # Test various failure points
        error_scenarios = [
            {
                "name": "Claude client unavailable",
                "patches": [('get_claude_client', Mock(return_value=None))],
                "expected_status": 503,
                "expected_message": "Horoscope service not available"
            },
            {
                "name": "Transit generation fails",
                "patches": [
                    ('get_claude_client', Mock()),
                    ('generate_transits', Mock(side_effect=Exception("Transit calculation error")))
                ],
                "expected_status": 500,
                "expected_message": "Failed to generate horoscope"
            },
            {
                "name": "Claude API fails",
                "patches": [
                    ('get_claude_client', Mock()),
                    ('generate_transits', Mock(return_value=(Mock(), []))),
                    ('call_claude_with_analytics', Mock(side_effect=Exception("Claude API error")))
                ],
                "expected_status": 500,
                "expected_message": "Failed to generate horoscope"
            }
        ]
        
        for scenario in error_scenarios:
            with self.subTest(scenario=scenario["name"]):
                patches = {key: value for key, value in scenario["patches"]}
                with patch.multiple('routes', **patches):
                    
                    with self.assertRaises(HTTPException) as context:
                        asyncio.run(generate_horoscope(request, user))
                    
                    self.assertEqual(context.exception.status_code, scenario["expected_status"])
                    self.assertIn(scenario["expected_message"], context.exception.detail)
    
    def test_different_birth_locations_integration(self):
        """Test horoscope generation for different birth locations."""
        from routes import generate_horoscope
        
        # Test locations with different time zones and coordinates
        test_locations = [
            {
                "name": "New York",
                "birth_data": BirthData(
                    birth_date="1990-12-25",
                    birth_time="09:00",
                    latitude=40.7128,
                    longitude=-74.0060
                ),
                "current_location": CurrentLocation(latitude=40.7128, longitude=-74.0060)
            },
            {
                "name": "Tokyo",
                "birth_data": BirthData(
                    birth_date="1985-03-15",
                    birth_time="18:30",
                    latitude=35.6762,
                    longitude=139.6503
                ),
                "current_location": CurrentLocation(latitude=35.6762, longitude=139.6503)
            },
            {
                "name": "Sydney",
                "birth_data": BirthData(
                    birth_date="1992-08-08",
                    birth_time="12:15",
                    latitude=-33.8688,
                    longitude=151.2093
                ),
                "current_location": CurrentLocation(latitude=-33.8688, longitude=151.2093)
            }
        ]
        
        for location_data in test_locations:
            with self.subTest(location=location_data["name"]):
                request = HoroscopeRequest(
                    birth_data=location_data["birth_data"],
                    current_location=location_data["current_location"],
                    horoscope_type=HoroscopePeriod.WEEK
                )
                
                with patch('routes.get_claude_client') as mock_get_claude:
                    with patch('routes.generate_transits') as mock_generate_transits:
                        with patch('routes.call_claude_with_analytics') as mock_call_claude:
                            
                            # Setup mocks
                            mock_transits = self._create_realistic_transits_response()
                            mock_charts = self._create_realistic_charts_response(7)
                            mock_generate_transits.return_value = (mock_transits, mock_charts)
                            
                            mock_claude_response = self._create_realistic_claude_response("weekly")
                            mock_call_claude.return_value = mock_claude_response
                            
                            mock_get_claude.return_value = Mock()
                            
                            # Execute pipeline
                            user = {'uid': f'location-test-{location_data["name"].lower()}'}
                            result = asyncio.run(generate_horoscope(request, user))
                            
                            # Verify success for all locations
                            self.assertIsInstance(result, HoroscopeResponse)
                            self.assertGreater(len(result.overall_summary), 50)
                            self.assertEqual(len(result.chart_urls), 7)
                            
                            # Verify that generate_transits was called with location-specific data
                            mock_generate_transits.assert_called_once_with(
                                location_data["birth_data"],
                                location_data["current_location"],
                                HoroscopePeriod.WEEK
                            )
    
    def test_analytics_integration(self):
        """Test that analytics are properly tracked during horoscope generation."""
        from routes import generate_horoscope
        
        request = HoroscopeRequest(
            birth_data=self.test_birth_data,
            current_location=self.test_location,
            horoscope_type=HoroscopePeriod.WEEK
        )
        
        with patch('routes.get_claude_client') as mock_get_claude:
            with patch('routes.generate_transits') as mock_generate_transits:
                with patch('routes.call_claude_with_analytics') as mock_call_claude:
                    
                    # Setup mocks
                    mock_transits = self._create_realistic_transits_response()
                    mock_charts = self._create_realistic_charts_response(7)
                    mock_generate_transits.return_value = (mock_transits, mock_charts)
                    
                    # Mock analytics tracking
                    mock_claude_response = self._create_realistic_claude_response("weekly")
                    mock_call_claude.return_value = mock_claude_response
                    
                    mock_get_claude.return_value = Mock()
                    
                    # Execute pipeline
                    user = {'uid': 'analytics-test-user'}
                    result = asyncio.run(generate_horoscope(request, user))
                    
                    # Verify that analytics wrapper was called
                    mock_call_claude.assert_called_once()
                    
                    # Verify analytics parameters
                    call_args = mock_call_claude.call_args
                    self.assertEqual(call_args.kwargs['endpoint_name'], 'generate-horoscope')
                    self.assertEqual(call_args.kwargs['user_id'], 'analytics-test-user')
                    
                    # Verify that the result is still correct
                    self.assertIsInstance(result, HoroscopeResponse)
    
    def _create_realistic_transits_response(self, num_days=7):
        """Create a realistic transits response for testing."""
        from kerykeion.kr_types.kr_models import TransitsTimeRangeModel
        from unittest.mock import Mock
        
        mock_transits = []
        base_date = datetime.now()
        
        for i in range(num_days):
            date = base_date + timedelta(days=i)
            
            # Create mock aspects for each day
            aspects = []
            aspect_types = ["Conjunction", "Opposition", "Trine", "Square", "Sextile"]
            planets = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"]
            
            for j in range((i % 3) + 1):  # 1-3 aspects per day
                aspect = Mock()
                aspect.aspect = aspect_types[j % len(aspect_types)]
                aspect.p1_name = planets[j % len(planets)]
                aspect.p2_name = planets[(j + 1) % len(planets)]
                aspect.orbit = 1.0 + (j * 0.5)
                aspect.aspect_degrees = j * 60
                aspects.append(aspect)
            
            transit_moment = Mock()
            transit_moment.date = date.strftime("%Y-%m-%d")
            transit_moment.aspects = aspects
            
            mock_transits.append(transit_moment)
        
        mock_model = Mock(spec=TransitsTimeRangeModel)
        mock_model.transits = mock_transits
        
        return mock_model
    
    def _create_realistic_charts_response(self, num_charts):
        """Create realistic charts response for testing."""
        from models import CosmiclogicalChart, PlanetPosition, HousePosition, SignData
        
        charts = []
        
        for i in range(num_charts):
            planets = {
                "Sun": PlanetPosition(
                    name="Sun",
                    sign="Gemini",
                    house=10,
                    degree=20.0 + (i * 0.5),
                    retrograde=False
                ),
                "Moon": PlanetPosition(
                    name="Moon",
                    sign="Cancer",
                    house=11,
                    degree=15.0 + (i * 2),
                    retrograde=False
                ),
                "Mercury": PlanetPosition(
                    name="Mercury",
                    sign="Gemini",
                    house=10,
                    degree=18.0 + i,
                    retrograde=i % 3 == 0  # Every third chart has Mercury retrograde
                )
            }
            
            houses = {
                "house_1": HousePosition(house=1, sign="Leo", degree=0.0),
                "house_10": HousePosition(house=10, sign="Gemini", degree=20.0)
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
                chartSvg=f"<svg>realistic chart {i}</svg>",
                chartImageUrl=f"https://example.com/realistic-chart-{i}.svg"
            )
            
            charts.append(chart)
        
        return charts
    
    def _create_realistic_claude_response(self, period_type):
        """Create a realistic Claude API response for testing."""
        from anthropic.types import TextBlock
        from unittest.mock import Mock
        
        # Realistic horoscope content based on period
        content_templates = {
            "weekly": '''
"overvall_summary": "This week emphasizes communication and social connections. The planetary alignments suggest favorable conditions for networking and creative expression. Pay attention to opportunities that arise through conversations.",
"specific_findings": [
    {
        "date": "2024-06-15",
        "horoscope": "Monday brings fresh energy with the Sun-Mercury conjunction. Focus on important communications and decision-making.",
        "active_aspects": ["Sun conjunction Mercury"],
        "retrograding_planets": []
    },
    {
        "date": "2024-06-16", 
        "horoscope": "Tuesday's Venus trine Mars creates harmony in relationships and collaborative efforts.",
        "active_aspects": ["Venus trine Mars"],
        "retrograding_planets": []
    },
    {
        "date": "2024-06-17",
        "horoscope": "Wednesday may present some challenges with Jupiter square Saturn, requiring patience and persistence.",
        "active_aspects": ["Jupiter square Saturn"],
        "retrograding_planets": ["Mercury"]
    }
]
}''',
            "monthly": '''
"overvall_summary": "This month brings significant growth opportunities in career and personal relationships. The emphasis is on building lasting foundations and expressing your authentic self. Major planetary transits support long-term planning.",
"specific_findings": [
    {
        "date": "2024-06-15",
        "horoscope": "The first half of the month focuses on career advancement and professional recognition.",
        "active_aspects": ["Sun trine Jupiter", "Venus conjunction Moon"],
        "retrograding_planets": []
    },
    {
        "date": "2024-06-30",
        "horoscope": "Month's end brings relationship clarity and emotional healing through compassionate communication.",
        "active_aspects": ["Moon sextile Neptune"],
        "retrograding_planets": ["Mercury"]
    }
]
}''',
            "yearly": '''
"overvall_summary": "This year marks a transformative period of personal evolution and spiritual growth. Major life themes include expanding your horizons, deepening relationships, and discovering your true purpose. The cosmos supports bold initiatives and authentic self-expression.",
"specific_findings": [
    {
        "date": "2024-06-15",
        "horoscope": "Summer months bring opportunities for travel, learning, and expanding your worldview.",
        "active_aspects": ["Jupiter trine Sun", "Saturn sextile Moon"],
        "retrograding_planets": []
    },
    {
        "date": "2024-12-15", 
        "horoscope": "Year's end focuses on integration of lessons learned and preparation for the next phase of growth.",
        "active_aspects": ["Pluto conjunction Mars"],
        "retrograding_planets": ["Mercury", "Venus"]
    }
]
}'''
        }
        
        mock_text_block = Mock(spec=TextBlock)
        mock_text_block.text = content_templates.get(period_type, content_templates["weekly"])
        
        mock_usage = Mock()
        mock_usage.input_tokens = 1000
        mock_usage.output_tokens = 300
        
        mock_response = Mock()
        mock_response.content = [mock_text_block]
        mock_response.usage = mock_usage
        
        return mock_response


if __name__ == "__main__":
    unittest.main(verbosity=2)