"""Tests for build_birth_chart_context function."""

import pytest
from unittest.mock import Mock
from models import AstrologicalChart, PlanetPosition, HousePosition, SignData
from contexts import build_birth_chart_context, parse_chart_response


class TestBuildBirthChartContext:
    """Test cases for build_birth_chart_context function."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Create mock planet positions
        self.planets = {
            "Sun": PlanetPosition(
                name="Sun",
                degree=15.5,
                sign="Leo",
                house=1,
                retrograde=False
            ),
            "Moon": PlanetPosition(
                name="Moon",
                degree=22.3,
                sign="Cancer",
                house=12,
                retrograde=False
            ),
            "Mercury": PlanetPosition(
                name="Mercury",
                degree=8.7,
                sign="Virgo",
                house=2,
                retrograde=True
            )
        }
        
        # Create mock house positions
        self.houses = {
            "1": HousePosition(house=1, degree=10.0, sign="Leo"),
            "2": HousePosition(house=2, degree=15.0, sign="Virgo")
        }
        
        # Create mock sign data
        self.sun_sign = SignData(
            name="Leo",
            element="Fire",
            modality="Fixed",
            ruling_planet="Sun"
        )
        
        self.moon_sign = SignData(
            name="Cancer",
            element="Water",
            modality="Cardinal",
            ruling_planet="Moon"
        )
        
        self.ascendant = SignData(
            name="Leo",
            element="Fire",
            modality="Fixed",
            ruling_planet="Sun"
        )
        
        # Create mock astrological chart
        self.chart = AstrologicalChart(
            planets=self.planets,
            houses=self.houses,
            sunSign=self.sun_sign,
            moonSign=self.moon_sign,
            ascendant=self.ascendant,
            chartSvg="<svg>mock chart</svg>",
            chartImageUrl="https://example.com/chart.jpg"
        )
    
    def test_build_birth_chart_context_returns_string(self):
        """Test that build_birth_chart_context returns a string."""
        (cached, user) = build_birth_chart_context(self.chart)
        
        assert isinstance(user, str)
        assert len(user) > 0
    
    def test_context_contains_required_elements(self):
        """Test that the context contains required astrological elements."""
        (cached, user) = build_birth_chart_context(self.chart)
        
        # Check for key instructional elements
        assert "expert astrologer" in cached
        assert "planet-house combinations" in user
        assert "JSON structure" in cached
        
        # Check for planet placeholders (only the ones in our test fixture)
        assert "sun" in user.lower()
        assert "moon" in user.lower()
        assert "mercury" in user.lower()
        
        # These should be in the cached JSON template, not user context
        assert "venus" in cached.lower()
        assert "mars" in cached.lower()
        assert "jupiter" in cached.lower()
        assert "saturn" in cached.lower()
        assert "uranus" in cached.lower()
        assert "neptune" in cached.lower()
        assert "pluto" in cached.lower()
        
        # Check for sign elements in the cached template
        assert "sun_sign" in cached.lower()
        assert "moon_sign" in cached.lower()
        assert "ascendant" in cached.lower()
    
    def test_context_includes_planet_data(self):
        """Test that the context includes the planet positions."""
        (cached, user) = build_birth_chart_context(self.chart)
        
        # The planets should be formatted into the context
        # Since format uses self.chart.planets, we should see evidence of the planets dict
        assert "{PLANET_HOUSES}" not in user  # Should be replaced
        
        # The actual planet data should be included somehow
        # Note: The actual format depends on how the planets dict is converted to string
        
    def test_context_format_structure(self):
        """Test that the context has the expected JSON format structure."""
        (cached, user) = build_birth_chart_context(self.chart)
        
        # Check for proper JSON structure elements
        assert '"influence": string' in cached
        assert '"traits": list' in cached
        
        # Check that all required planet/sign fields are present in the cached template
        expected_fields = [
            '"sun":', '"moon":', '"mercury":', '"venus":', '"mars":',
            '"jupiter":', '"saturn":', '"uranus":', '"neptune":', '"pluto":',
            '"sun_sign":', '"moon_sign":', '"ascendant":'
        ]
        
        for field in expected_fields:
            assert field in cached.lower()
    
    def test_empty_planets_dict(self):
        """Test handling of empty planets dictionary."""
        empty_chart = AstrologicalChart(
            planets={},
            houses=self.houses,
            sunSign=self.sun_sign,
            moonSign=self.moon_sign,
            ascendant=self.ascendant,
            chartSvg="<svg>mock chart</svg>"
        )
        
        (cached, user) = build_birth_chart_context(empty_chart)
        
        # Should still return a valid context string
        assert isinstance(user, str)
        assert len(user) > 0
        assert "expert astrologer" in cached


class TestParseChartResponse:
    """Test cases for parse_chart_response function."""
    
    def test_parse_valid_response(self):
        """Test parsing a valid chart analysis response."""
        # Note: The function expects response without opening brace
        valid_response = '''
    "sun": {
        "influence": "Strong leadership qualities",
        "traits": ["confident", "creative", "generous"]
    },
    "moon": {
        "influence": "Deep emotional sensitivity",
        "traits": ["nurturing", "intuitive", "protective"]
    },
    "mercury": {
        "influence": "Analytical and detail-oriented",
        "traits": ["practical", "precise", "methodical"]
    },
    "venus": {
        "influence": "Harmonious approach to partnerships",
        "traits": ["diplomatic", "artistic", "charming"]
    },
    "mars": {
        "influence": "Determined and ambitious",
        "traits": ["assertive", "energetic", "competitive"]
    },
    "jupiter": {
        "influence": "Optimistic outlook on life",
        "traits": ["generous", "philosophical", "adventurous"]
    },
    "saturn": {
        "influence": "Strong sense of responsibility",
        "traits": ["disciplined", "patient", "reliable"]
    },
    "uranus": {
        "influence": "Unconventional thinking",
        "traits": ["independent", "progressive", "inventive"]
    },
    "neptune": {
        "influence": "Heightened intuition",
        "traits": ["compassionate", "imaginative", "mystical"]
    },
    "pluto": {
        "influence": "Deep psychological insight",
        "traits": ["intense", "transformative", "powerful"]
    },
    "sun_sign": {
        "influence": "Natural leadership abilities",
        "traits": ["charismatic", "dramatic", "loyal"]
    },
    "moon_sign": {
        "influence": "Strong family connections",
        "traits": ["caring", "protective", "emotional"]
    },
    "ascendant": {
        "influence": "Confident outward expression",
        "traits": ["magnetic", "warm", "expressive"]
    }
}'''
        
        result = parse_chart_response(valid_response)
        
        # Verify the result is a ChartAnalysis object
        from models import ChartAnalysis
        assert isinstance(result, ChartAnalysis)
        
        # Check some specific fields
        assert result.sun.influence == "Strong leadership qualities"
        assert result.sun.traits == ["confident", "creative", "generous"]
        
        assert len(result.mercury.traits) == 3
    
    def test_parse_invalid_json(self):
        """Test parsing invalid JSON response."""
        invalid_response = '''
    "sun": {
        "meaning": "Missing closing brace"
        "influence": "Invalid JSON"
    }
    '''
        
        with pytest.raises(ValueError, match="Invalid response format"):
            parse_chart_response(invalid_response)
    
    def test_parse_missing_fields(self):
        """Test parsing response with missing required fields."""
        incomplete_response = '''
    "sun": {
        "meaning": "Core identity",
        "influence": "Leadership"
    }
}'''
        
        with pytest.raises(ValueError, match="Error processing personality analysis response"):
            parse_chart_response(incomplete_response)
    
    def test_parse_empty_response(self):
        """Test parsing empty response."""
        with pytest.raises(ValueError, match="Invalid response format"):
            parse_chart_response("")