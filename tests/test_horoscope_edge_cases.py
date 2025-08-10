"""Edge case tests for horoscope functionality."""

import unittest
from unittest.mock import Mock, patch
from datetime import datetime
from models import (
    HoroscopePeriod, CosmiclogicalChart, PlanetPosition, HousePosition, SignData
)
from contexts import build_horoscope_context
from kerykeion.kr_types.kr_models import TransitsTimeRangeModel
from config import get_claude_client


class MockComplexAspect:
    """Mock class for complex aspects with missing attributes."""
    
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class MockTransitMomentWithComplexData:
    """Mock transit moment with complex aspect data."""
    
    def __init__(self, date_str, aspects=None, extra_data=None):
        self.date = date_str
        self.aspects = aspects or []
        if extra_data:
            for key, value in extra_data.items():
                setattr(self, key, value)


class TestHoroscopeEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions in horoscope functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Initialize Claude client for token counting
        self.claude_client = get_claude_client()
    
    def count_tokens(self, text):
        """Count tokens in text using Claude's token counting."""
        try:
            response = self.claude_client.messages.count_tokens(
                model="claude-3-5-sonnet-20241022",
                messages=[{
                    "role": "user", 
                    "content": text
                }]
            )
            return response.input_tokens
        except Exception as e:
            # Fallback: rough approximation (4 chars per token)
            return len(text) // 4
    
    def test_horoscope_context_with_missing_aspect_attributes(self):
        """Test horoscope context generation when aspects have missing attributes."""
        # Create aspects with missing attributes
        incomplete_aspects = [
            MockComplexAspect(aspect="Conjunction", p1_name="Sun"),  # Missing p2_name
            MockComplexAspect(p1_name="Moon", p2_name="Venus"),  # Missing aspect type
            MockComplexAspect(aspect="Trine"),  # Missing planet names
            MockComplexAspect()  # Completely empty aspect
        ]
        
        mock_transits = [
            MockTransitMomentWithComplexData("2024-06-15", incomplete_aspects)
        ]
        
        mock_model = Mock(spec=TransitsTimeRangeModel)
        mock_model.transits = mock_transits
        
        # Create minimal chart
        mock_chart = self._create_minimal_chart()
        
        # Should not raise an exception
        system, user = build_horoscope_context(mock_model, [mock_chart], HoroscopePeriod.WEEK)
        
        # Verify it still produces valid context
        self.assertIsInstance(system, str)
        self.assertIsInstance(user, str)
        self.assertIn("astrology guru", system)
        
        # Check that it gracefully handles missing attributes
        self.assertIn("Unknown", user)  # Should contain fallback values
    
    def test_horoscope_context_with_none_values(self):
        """Test horoscope context generation with None values in data."""
        # Create transit with None values
        mock_transits = [
            MockTransitMomentWithComplexData(None, None)  # Both date and aspects are None
        ]
        
        mock_model = Mock(spec=TransitsTimeRangeModel)
        mock_model.transits = mock_transits
        
        mock_chart = self._create_minimal_chart()
        
        # Should handle None values gracefully
        system, user = build_horoscope_context(mock_model, [mock_chart], HoroscopePeriod.MONTH)
        
        self.assertIsInstance(system, str)
        self.assertIsInstance(user, str)
        self.assertIn("Unknown", user)  # Should use fallback for None date
    
    def test_horoscope_context_with_malformed_dates(self):
        """Test horoscope context generation with malformed date strings."""
        malformed_aspects = [
            MockComplexAspect(aspect="Square", p1_name="Mars", p2_name="Jupiter", orbit="invalid", aspect_degrees="not_a_number")
        ]
        
        mock_transits = [
            MockTransitMomentWithComplexData("invalid-date-format", malformed_aspects),
            MockTransitMomentWithComplexData("2024-13-45", malformed_aspects),  # Invalid date
            MockTransitMomentWithComplexData("", malformed_aspects)  # Empty date
        ]
        
        mock_model = Mock(spec=TransitsTimeRangeModel)
        mock_model.transits = mock_transits
        
        mock_chart = self._create_minimal_chart()
        
        # Should handle malformed dates without crashing
        system, user = build_horoscope_context(mock_model, [mock_chart], HoroscopePeriod.YEAR)
        
        self.assertIsInstance(system, str)
        self.assertIsInstance(user, str)
    
    def test_horoscope_context_with_massive_data(self):
        """Test horoscope context generation with realistic yearly horoscope data (12 months)."""
        # Create aspects with realistic complexity
        large_aspects = []
        for i in range(50):  # More realistic number of aspects
            large_aspects.append(
                MockComplexAspect(
                    aspect=f"Aspect_{i}",
                    p1_name=f"Planet_{i % 10}",
                    p2_name=f"Planet_{(i + 1) % 10}",
                    orbit=i * 0.1,
                    aspect_degrees=i * 3.6
                )
            )
        
        mock_transits = []
        for i in range(12):  # One transit per month for yearly horoscope
            from datetime import timedelta
            date = datetime(2024, i + 1, 15)  # 15th of each month
            date_str = date.strftime("%Y-%m-%d")
            # Each month has 3-5 aspects
            daily_aspects = large_aspects[i * 3:(i * 3) + 4]
            mock_transits.append(MockTransitMomentWithComplexData(date_str, daily_aspects))
        
        mock_model = Mock(spec=TransitsTimeRangeModel)
        mock_model.transits = mock_transits
        
        # Create charts for yearly horoscope (12 monthly charts)
        mock_charts = [self._create_minimal_chart(f"chart_{i}") for i in range(12)]
        
        # Generate context and measure performance
        import time
        start_time = time.time()
        
        system, user = build_horoscope_context(mock_model, mock_charts, HoroscopePeriod.YEAR)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Verify it completes in reasonable time (less than 1 second for yearly data)
        self.assertLess(processing_time, 1.0, "Context generation took too long")
        
        # Verify output quality
        self.assertIsInstance(system, str)
        self.assertIsInstance(user, str)
        self.assertGreater(len(user), 500)  # Should have substantial content
        
        # Check token count for cost estimation
        total_tokens = self.count_tokens(system + user)
        print(f"\nYearly dataset context - Tokens: {total_tokens:,}, Time: {processing_time:.2f}s")
        
        # Should be manageable for Claude (under 20k tokens for yearly)
        self.assertLess(total_tokens, 20000, "Context too large for yearly horoscope")
    
    def test_horoscope_context_with_unicode_and_special_characters(self):
        """Test horoscope context generation with unicode and special characters."""
        unicode_aspects = [
            MockComplexAspect(
                aspect="Conjunction ☌",
                p1_name="Sun ☉",
                p2_name="Moon ☽",
                orbit=1.5,
                aspect_degrees=0
            ),
            MockComplexAspect(
                aspect="Opposition ☍",
                p1_name="Mars ♂",
                p2_name="Venus ♀",
                orbit=2.8,
                aspect_degrees=180
            ),
            MockComplexAspect(
                aspect="Trine △",
                p1_name="Jupiter ♃",
                p2_name="Saturn ♄",
                orbit=3.1,
                aspect_degrees=120
            )
        ]
        
        mock_transits = [
            MockTransitMomentWithComplexData("2024-06-15", unicode_aspects)
        ]
        
        mock_model = Mock(spec=TransitsTimeRangeModel)
        mock_model.transits = mock_transits
        
        # Create chart with unicode planet names
        unicode_chart = self._create_chart_with_unicode()
        
        system, user = build_horoscope_context(mock_model, [unicode_chart], HoroscopePeriod.WEEK)
        
        # Should handle unicode correctly
        self.assertIsInstance(system, str)
        self.assertIsInstance(user, str)
        self.assertIn("☌", user)  # Should preserve unicode symbols
        self.assertIn("♂", user)
        self.assertIn("♀", user)
    
    def test_horoscope_context_with_extreme_coordinates(self):
        """Test horoscope context generation with charts from extreme geographic locations."""
        # Create charts for extreme locations (North Pole, South Pole, etc.)
        extreme_charts = []
        
        extreme_locations = [
            {"name": "North_Pole", "lat": 90.0, "lon": 0.0},
            {"name": "South_Pole", "lat": -90.0, "lon": 0.0},
            {"name": "Date_Line", "lat": 0.0, "lon": 180.0},
            {"name": "Prime_Meridian", "lat": 0.0, "lon": 0.0}
        ]
        
        for location in extreme_locations:
            chart = self._create_minimal_chart(location["name"])
            extreme_charts.append(chart)
        
        mock_transits = [
            MockTransitMomentWithComplexData("2024-06-21", [  # Summer solstice
                MockComplexAspect(aspect="Conjunction", p1_name="Sun", p2_name="Cancer", orbit=0.0)
            ])
        ]
        
        mock_model = Mock(spec=TransitsTimeRangeModel)
        mock_model.transits = mock_transits
        
        # Should handle extreme coordinates without issues
        system, user = build_horoscope_context(mock_model, extreme_charts, HoroscopePeriod.WEEK)
        
        self.assertIsInstance(system, str)
        self.assertIsInstance(user, str)
        self.assertIn("astrology guru", system)
    
    def test_horoscope_context_empty_transits_list(self):
        """Test horoscope context generation with completely empty transits."""
        mock_model = Mock(spec=TransitsTimeRangeModel)
        mock_model.transits = []  # Completely empty
        
        mock_chart = self._create_minimal_chart()
        
        system, user = build_horoscope_context(mock_model, [mock_chart], HoroscopePeriod.WEEK)
        
        # Should still generate valid context
        self.assertIsInstance(system, str)
        self.assertIsInstance(user, str)
        self.assertIn("astrology guru", system)
        
        # Should contain empty list representation
        self.assertIn("[]", user)  # Empty transits list
    
    def test_horoscope_context_token_efficiency(self):
        """Test token efficiency across different horoscope types."""
        mock_model = self._create_realistic_transit_model()
        mock_charts = [self._create_minimal_chart() for _ in range(30)]  # Month worth of charts
        
        results = {}
        
        for period in [HoroscopePeriod.WEEK, HoroscopePeriod.MONTH, HoroscopePeriod.YEAR]:
            system, user = build_horoscope_context(mock_model, mock_charts, period)
            
            total_tokens = self.count_tokens(system + user)
            cost_estimate = (total_tokens / 1000000) * 3  # Claude pricing
            
            results[period.value] = {
                "tokens": total_tokens,
                "cost": cost_estimate,
                "system_length": len(system),
                "user_length": len(user)
            }
            
            print(f"\n{period.value.upper()} Horoscope:")
            print(f"  Tokens: {total_tokens:,}")
            print(f"  Est. cost: ${cost_estimate:.6f}")
            print(f"  System length: {len(system):,} chars")
            print(f"  User length: {len(user):,} chars")
            
            # Verify reasonable token usage
            self.assertLess(total_tokens, 15000, f"{period.value} horoscope uses too many tokens")
            self.assertLess(cost_estimate, 0.05, f"{period.value} horoscope too expensive")
        
        # Verify that longer periods don't use exponentially more tokens
        week_tokens = results["week"]["tokens"]
        month_tokens = results["month"]["tokens"]
        year_tokens = results["year"]["tokens"]
        
        # Monthly should be at most 3x weekly
        self.assertLess(month_tokens, week_tokens * 3, "Monthly horoscope uses too many tokens relative to weekly")
        
        # Yearly should be at most 5x weekly (not 52x)
        self.assertLess(year_tokens, week_tokens * 5, "Yearly horoscope uses too many tokens relative to weekly")
    
    def _create_minimal_chart(self, name_suffix=""):
        """Create a minimal cosmiclogical chart for testing."""
        planets = {
            "Sun": PlanetPosition(
                name="Sun",
                sign="Gemini",
                house=10,
                degree=25.0,
                retrograde=False
            )
        }
        
        houses = {
            "house_1": HousePosition(house=1, sign="Leo", degree=0.0)
        }
        
        sun_sign = SignData(name="Gemini", element="Air", modality="Mutable", ruling_planet="Mercury")
        moon_sign = SignData(name="Cancer", element="Water", modality="Cardinal", ruling_planet="Moon")
        ascendant = SignData(name="Leo", element="Fire", modality="Fixed", ruling_planet="Sun")
        
        return CosmiclogicalChart(
            planets=planets,
            houses=houses,
            sunSign=sun_sign,
            moonSign=moon_sign,
            ascendant=ascendant,
            chartSvg=f"<svg>minimal chart {name_suffix}</svg>",
            chartImageUrl=f"https://example.com/chart-{name_suffix}.svg"
        )
    
    def _create_chart_with_unicode(self):
        """Create a chart with unicode planet names."""
        planets = {
            "Sun ☉": PlanetPosition(
                name="Sun ☉",
                sign="Gemini ♊",
                house=10,
                degree=25.0,
                retrograde=False
            ),
            "Moon ☽": PlanetPosition(
                name="Moon ☽",
                sign="Cancer ♋",
                house=11,
                degree=15.0,
                retrograde=False
            )
        }
        
        houses = {
            "house_1": HousePosition(house=1, sign="Leo ♌", degree=0.0)
        }
        
        sun_sign = SignData(name="Gemini ♊", element="Air", modality="Mutable", ruling_planet="Mercury ☿")
        moon_sign = SignData(name="Cancer ♋", element="Water", modality="Cardinal", ruling_planet="Moon ☽")
        ascendant = SignData(name="Leo ♌", element="Fire", modality="Fixed", ruling_planet="Sun ☉")
        
        return CosmiclogicalChart(
            planets=planets,
            houses=houses,
            sunSign=sun_sign,
            moonSign=moon_sign,
            ascendant=ascendant,
            chartSvg="<svg>unicode chart ♈♉♊♋♌♍♎♏♐♑♒♓</svg>",
            chartImageUrl="https://example.com/unicode-chart.svg"
        )
    
    def _create_realistic_transit_model(self):
        """Create a realistic transit model for testing."""
        realistic_aspects = [
            MockComplexAspect(aspect="Conjunction", p1_name="Sun", p2_name="Mercury", orbit=2.1, aspect_degrees=0),
            MockComplexAspect(aspect="Sextile", p1_name="Venus", p2_name="Mars", orbit=1.8, aspect_degrees=60),
            MockComplexAspect(aspect="Square", p1_name="Jupiter", p2_name="Saturn", orbit=3.2, aspect_degrees=90),
            MockComplexAspect(aspect="Trine", p1_name="Moon", p2_name="Neptune", orbit=2.5, aspect_degrees=120),
            MockComplexAspect(aspect="Opposition", p1_name="Mars", p2_name="Pluto", orbit=4.1, aspect_degrees=180)
        ]
        
        mock_transits = []
        for i in range(30):  # 30 days of realistic transits
            date = datetime(2024, 6, 1 + i)
            date_str = date.strftime("%Y-%m-%d")
            
            # Each day has 2-4 aspects
            daily_aspects = realistic_aspects[(i * 2) % len(realistic_aspects):(i * 2 + 3) % len(realistic_aspects)]
            mock_transits.append(MockTransitMomentWithComplexData(date_str, daily_aspects))
        
        mock_model = Mock(spec=TransitsTimeRangeModel)
        mock_model.transits = mock_transits
        
        return mock_model


if __name__ == "__main__":
    unittest.main(verbosity=2)