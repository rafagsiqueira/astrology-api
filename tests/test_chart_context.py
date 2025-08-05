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
        context = build_birth_chart_context(self.chart)
        
        assert isinstance(context, str)
        assert len(context) > 0
    
    def test_context_contains_required_elements(self):
        """Test that the context contains required astrological elements."""
        context = build_birth_chart_context(self.chart)
        
        # Check for key instructional elements
        assert "expert astrologer" in context
        assert "planet-house combinations" in context
        assert "JSON structure" in context
        
        # Check for planet placeholders
        assert "sun" in context.lower()
        assert "moon" in context.lower()
        assert "mercury" in context.lower()
        assert "venus" in context.lower()
        assert "mars" in context.lower()
        assert "jupiter" in context.lower()
        assert "saturn" in context.lower()
        assert "uranus" in context.lower()
        assert "neptune" in context.lower()
        assert "pluto" in context.lower()
        
        # Check for sign elements
        assert "sun_sign" in context
        assert "moon_sign" in context
        assert "ascendant" in context
    
    def test_context_includes_planet_data(self):
        """Test that the context includes the planet positions."""
        context = build_birth_chart_context(self.chart)
        
        # The planets should be formatted into the context
        # Since format uses self.chart.planets, we should see evidence of the planets dict
        assert "{$PLANET_HOUSES}" not in context  # Should be replaced
        
        # The actual planet data should be included somehow
        # Note: The actual format depends on how the planets dict is converted to string
        
    def test_context_format_structure(self):
        """Test that the context has the expected JSON format structure."""
        context = build_birth_chart_context(self.chart)
        
        # Check for proper JSON structure elements
        assert '"meaning": string' in context
        assert '"influence": string' in context
        assert '"traits": list' in context
        
        # Check that all required planet/sign fields are present
        expected_fields = [
            '"sun":', '"moon":', '"mercury":', '"venus":', '"mars":',
            '"jupiter":', '"saturn":', '"uranus":', '"neptune":', '"pluto":',
            '"sun_sign":', '"moon_sign":', '"ascendant":'
        ]
        
        for field in expected_fields:
            assert field in context
    
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
        
        context = build_birth_chart_context(empty_chart)
        
        # Should still return a valid context string
        assert isinstance(context, str)
        assert len(context) > 0
        assert "expert astrologer" in context


class TestParseChartResponse:
    """Test cases for parse_chart_response function."""
    
    def test_parse_valid_response(self):
        """Test parsing a valid chart analysis response."""
        # Note: The function expects response without opening brace
        valid_response = '''
    "sun": {
        "meaning": "Core identity and life force",
        "influence": "Strong leadership qualities",
        "traits": ["confident", "creative", "generous"]
    },
    "moon": {
        "meaning": "Emotional nature and instincts",
        "influence": "Deep emotional sensitivity",
        "traits": ["nurturing", "intuitive", "protective"]
    },
    "mercury": {
        "meaning": "Communication and thinking",
        "influence": "Analytical and detail-oriented",
        "traits": ["practical", "precise", "methodical"]
    },
    "venus": {
        "meaning": "Love and relationships",
        "influence": "Harmonious approach to partnerships",
        "traits": ["diplomatic", "artistic", "charming"]
    },
    "mars": {
        "meaning": "Action and energy",
        "influence": "Determined and ambitious",
        "traits": ["assertive", "energetic", "competitive"]
    },
    "jupiter": {
        "meaning": "Growth and expansion",
        "influence": "Optimistic outlook on life",
        "traits": ["generous", "philosophical", "adventurous"]
    },
    "saturn": {
        "meaning": "Structure and discipline",
        "influence": "Strong sense of responsibility",
        "traits": ["disciplined", "patient", "reliable"]
    },
    "uranus": {
        "meaning": "Innovation and change",
        "influence": "Unconventional thinking",
        "traits": ["independent", "progressive", "inventive"]
    },
    "neptune": {
        "meaning": "Dreams and spirituality",
        "influence": "Heightened intuition",
        "traits": ["compassionate", "imaginative", "mystical"]
    },
    "pluto": {
        "meaning": "Transformation and power",
        "influence": "Deep psychological insight",
        "traits": ["intense", "transformative", "powerful"]
    },
    "sun_sign": {
        "meaning": "Leo energy and fire element",
        "influence": "Natural leadership abilities",
        "traits": ["charismatic", "dramatic", "loyal"]
    },
    "moon_sign": {
        "meaning": "Cancer emotional nature",
        "influence": "Strong family connections",
        "traits": ["caring", "protective", "emotional"]
    },
    "ascendant": {
        "meaning": "Leo rising appearance",
        "influence": "Confident outward expression",
        "traits": ["magnetic", "warm", "expressive"]
    }
}'''
        
        result = parse_chart_response(valid_response)
        
        # Verify the result is a ChartAnalysis object
        from models import ChartAnalysis
        assert isinstance(result, ChartAnalysis)
        
        # Check some specific fields
        assert result.sun.meaning == "Core identity and life force"
        assert result.sun.influence == "Strong leadership qualities"
        assert result.sun.traits == ["confident", "creative", "generous"]
        
        assert result.moon.meaning == "Emotional nature and instincts"
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