import unittest
from unittest.mock import Mock
from models import AstrologicalChart, PlanetPosition, HousePosition, SignData
from contexts import build_birth_chart_context, parse_chart_response

class TestBuildBirthChartContext(unittest.TestCase):
    """Test cases for build_birth_chart_context function."""
    
    def setUp(self):
        """Set up test fixtures."""
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
        
        self.houses = {
            "1": HousePosition(house=1, degree=10.0, sign="Leo"),
            "2": HousePosition(house=2, degree=15.0, sign="Virgo")
        }
        
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
        
        self.chart = AstrologicalChart(
            planets=self.planets,
            houses=self.houses,
            sun_sign=self.sun_sign,
            moon_sign=self.moon_sign,
            ascendant=self.ascendant,
            light_svg="<svg>mock chart</svg>",
            dark_svg="<svg>mock chart</svg>"
        )
    
    def test_build_birth_chart_context_returns_string(self):
        """Test that build_birth_chart_context returns a string."""
        (cached, user) = build_birth_chart_context(self.chart)
        
        self.assertIsInstance(user, str)
        self.assertGreater(len(user), 0)
    
    def test_context_contains_required_elements(self):
        """Test that the context contains required astrological elements."""
        (cached, user) = build_birth_chart_context(self.chart)
        
        self.assertIn("expert astrologer", cached)
        self.assertIn("planet-house combinations", user)
        self.assertIn("JSON format", cached)
        
        self.assertIn("sun", user.lower())
        self.assertIn("moon", user.lower())
        self.assertIn("mercury", user.lower())
        
        self.assertIn("venus", cached.lower())
        self.assertIn("mars", cached.lower())
        self.assertIn("jupiter", cached.lower())
        self.assertIn("saturn", cached.lower())
        self.assertIn("uranus", cached.lower())
        self.assertIn("neptune", cached.lower())
        self.assertIn("pluto", cached.lower())
        
        self.assertIn("ascendant", cached.lower())
    
    def test_context_includes_planet_data(self):
        """Test that the context includes the planet positions."""
        (cached, user) = build_birth_chart_context(self.chart)
        
        self.assertNotIn("{PLANET_HOUSES}", user)

    def test_context_format_structure(self):
        """Test that the context has the expected JSON format structure."""
        (cached, user) = build_birth_chart_context(self.chart)
        
        self.assertIn('"influence": string', cached)
        self.assertIn('"traits": list', cached)
        
        expected_fields = [
            '"sun":', '"moon":', '"mercury":', '"venus":', '"mars":',
            '"jupiter":', '"saturn":', '"uranus":', '"neptune":', '"pluto":',
            '"ascendant":'
        ]
        
        for field in expected_fields:
            self.assertIn(field, cached.lower())
    
    def test_empty_planets_dict(self):
        """Test handling of empty planets dictionary."""
        empty_chart = AstrologicalChart(
            planets={},
            houses=self.houses,
            sun_sign=self.sun_sign,
            moon_sign=self.moon_sign,
            ascendant=self.ascendant,
            light_svg="<svg>mock chart</svg>",
            dark_svg="<svg>mock chart</svg>"
        )
        
        (cached, user) = build_birth_chart_context(empty_chart)
        
        self.assertIsInstance(user, str)
        self.assertGreater(len(user), 0)
        self.assertIn("expert astrologer", cached)


class TestParseChartResponse(unittest.TestCase):
    """Test cases for parse_chart_response function."""
    
    def test_parse_valid_response(self):
        """Test parsing a valid chart analysis response."""
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
        
        from models import ChartAnalysis
        self.assertIsInstance(result, ChartAnalysis)
        
        self.assertEqual(result.sun.influence, "Strong leadership qualities")
        self.assertEqual(result.sun.traits, ["confident", "creative", "generous"])
        
        self.assertEqual(len(result.mercury.traits), 3)
    
    def test_parse_invalid_json(self):
        """Test parsing invalid JSON response."""
        invalid_response = '''
    "sun": {
        "meaning": "Missing closing brace"
        "influence": "Invalid JSON"
    }
    '''
        
        with self.assertRaisesRegex(ValueError, "Invalid response format"):
            parse_chart_response(invalid_response)
    
    def test_parse_missing_fields(self):
        """Test parsing response with missing required fields."""
        incomplete_response = '''
    "sun": {
        "meaning": "Core identity",
        "influence": "Leadership"
    }
}'''
        
        with self.assertRaisesRegex(ValueError, "Error processing personality analysis response"):
            parse_chart_response(incomplete_response)
    
    def test_parse_empty_response(self):
        """Test parsing empty response."""
        with self.assertRaisesRegex(ValueError, "Invalid response format"):
            parse_chart_response("")

if __name__ == '__main__':
    unittest.main()
