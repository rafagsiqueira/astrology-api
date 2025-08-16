"""Core context building and parsing tests - organized and comprehensive."""

import pytest
import unittest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from contexts import (
    build_birth_chart_context, parse_chart_response,
    build_personality_context, parse_personality_response,
    build_relationship_context, parse_relationship_response,
    build_chat_context, build_composite_context, parse_composite_response,
    build_horoscope_context
)
from models import (
    AstrologicalChart, PlanetPosition, HousePosition, SignData,
    PersonalityAnalysis, RelationshipAnalysis, CompositeAnalysis,
    BirthData, DailyTransit, AnalysisRequest, DailyTransitChange, TransitChanges, RetrogradeChanges
)


class TestBirthChartContext(unittest.TestCase):
    """Test birth chart context building and parsing."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_chart = self._create_mock_chart()
    
    def _create_mock_chart(self):
        """Create a mock astrological chart for testing."""
        planets = {
            'sun': PlanetPosition(
                name='Sun',
                sign='Leo',
                house=10,
                degree=15.5
            ),
            'moon': PlanetPosition(
                name='Moon',
                sign='Cancer',
                house=9,
                degree=23.2
            )
        }
        
        houses = {
            '1': HousePosition(house=1, sign='Scorpio', degree=5.0),
            '2': HousePosition(house=2, sign='Sagittarius', degree=10.0)
        }
        
        return AstrologicalChart(
            planets=planets,
            houses=houses,
            sun_sign=SignData(name='Leo', element='Fire', modality='Fixed', ruling_planet='Sun'),
            moon_sign=SignData(name='Cancer', element='Water', modality='Cardinal', ruling_planet='Moon'),
            ascendant=SignData(name='Scorpio', element='Water', modality='Fixed', ruling_planet='Pluto'),
            light_svg='<svg>mock chart</svg>',
            dark_svg='<svg>mock chart</svg>'
        )
    
    def test_build_birth_chart_context_structure(self):
        """Test that birth chart context returns proper structure."""
        system, user = build_birth_chart_context(self.mock_chart)
        
        self.assertIsInstance(system, str)
        self.assertIsInstance(user, str)
        self.assertGreater(len(system), 100)  # Should be substantial
        self.assertGreater(len(user), 50)
    
    def test_build_birth_chart_context_contains_planets(self):
        """Test that context contains planet information."""
        system, user = build_birth_chart_context(self.mock_chart)
        
        # Should contain planet names and signs
        self.assertIn('Sun', user)
        self.assertIn('Moon', user)
        self.assertIn('Leo', user)
        self.assertIn('Cancer', user)
    
    def test_parse_chart_response_valid_json(self):
        """Test parsing valid chart analysis response."""
        valid_json_response = '''"sun": {
            "influence": "Strong leadership and creativity",
            "traits": ["confident", "creative", "generous"]
        },
        "moon": {
            "influence": "Deep emotional nature and intuition",
            "traits": ["intuitive", "nurturing", "sensitive"]
        },
        "ascendant": {
            "influence": "Intense and transformative presence",
            "traits": ["magnetic", "determined", "perceptive"]
        },
        "mercury": {
            "influence": "Quick thinking and communication skills",
            "traits": ["articulate", "curious", "adaptable"]
        },
        "venus": {
            "influence": "Artistic and romantic nature",
            "traits": ["charming", "aesthetic", "harmonious"]
        },
        "mars": {
            "influence": "Dynamic energy and assertiveness",
            "traits": ["energetic", "passionate", "decisive"]
        },
        "jupiter": {
            "influence": "Optimism and expansion",
            "traits": ["optimistic", "philosophical", "generous"]
        },
        "saturn": {
            "influence": "Discipline and responsibility",
            "traits": ["disciplined", "responsible", "practical"]
        },
        "uranus": {
            "influence": "Innovation and independence",
            "traits": ["innovative", "independent", "unconventional"]
        },
        "neptune": {
            "influence": "Spiritual and imaginative tendencies",
            "traits": ["imaginative", "spiritual", "compassionate"]
        },
        "pluto": {
            "influence": "Transformation and deep insights",
            "traits": ["transformative", "intense", "insightful"]
        }
}'''
        
        analysis = parse_chart_response(valid_json_response)
        
        # Verify the analysis was parsed correctly
        self.assertEqual(analysis.sun.influence, "Strong leadership and creativity")
        self.assertIn("confident", analysis.sun.traits)
        self.assertEqual(analysis.moon.influence, "Deep emotional nature and intuition")
        self.assertIn("intuitive", analysis.moon.traits)
    
    def test_parse_chart_response_invalid_json(self):
        """Test parsing invalid JSON response."""
        invalid_response = "This is not valid JSON"
        
        with self.assertRaises(Exception):
            parse_chart_response(invalid_response)
    
    def test_build_birth_chart_context_empty_chart(self):
        """Test context building with empty chart data."""
        empty_chart = AstrologicalChart(
            planets={},
            houses={},
            sun_sign=SignData(name='Unknown', element='Unknown', modality='Unknown', ruling_planet='Unknown'),
            moon_sign=SignData(name='Unknown', element='Unknown', modality='Unknown', ruling_planet='Unknown'),
            ascendant=SignData(name='Unknown', element='Unknown', modality='Unknown', ruling_planet='Unknown'),
        )
        
        system, user = build_birth_chart_context(empty_chart)
        
        # Should still return strings, but indicate missing data
        self.assertIsInstance(system, str)
        self.assertIsInstance(user, str)


class TestPersonalityContext(unittest.TestCase):
    """Test personality analysis context building and parsing."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_chart = self._create_mock_chart()
    
    def _create_mock_chart(self):
        """Create a mock chart for personality testing."""
        planets = {
            'sun': PlanetPosition(name='Sun', sign='Gemini', house=3, degree=12.5),
            'moon': PlanetPosition(name='Moon', sign='Pisces', house=12, degree=8.3),
            'mercury': PlanetPosition(name='Mercury', sign='Gemini', house=3, degree=18.2)
        }
        
        return AstrologicalChart(
            planets=planets,
            houses={},
            sun_sign=SignData(name='Gemini', element='Air', modality='Mutable', ruling_planet='Mercury'),
            moon_sign=SignData(name='Pisces', element='Water', modality='Mutable', ruling_planet='Neptune'),
            ascendant=SignData(name='Gemini', element='Air', modality='Mutable', ruling_planet='Mercury'),
        )
    
    def test_build_personality_context_structure(self):
        """Test personality context structure."""
        analysis_request = AnalysisRequest(
            birth_date='1990-06-15',
            birth_time='12:00',
            latitude=40.7128,
            longitude=-74.0060
        )
        system, user = build_personality_context(analysis_request)
        
        self.assertIsInstance(system, str)
        self.assertIsInstance(user, str)
        self.assertIn('personality', system.lower())
    
    def test_parse_personality_response_valid(self):
        """Test parsing valid personality response."""
        valid_json_response = '''"overview": "A creative and intuitive individual with strong communication skills",
        "personality_traits": {
            "description": "Core personality characteristics",
            "key_traits": ["creative", "intuitive", "communicative", "adaptable"]
        },
        "emotional_nature": {
            "description": "Emotional processing and expression",
            "emotional_characteristics": ["sensitive", "empathetic", "emotionally intelligent"]
        },
        "communication_and_intellect": {
            "description": "Communication style and intellectual approach",
            "communication_strengths": ["articulate", "persuasive", "curious"]
        },
        "relationships_and_love": {
            "description": "Approach to relationships and love",
            "relationship_dynamics": ["loyal", "romantic", "supportive"]
        },
        "career_and_purpose": {
            "description": "Career inclinations and life purpose",
            "career_potential": ["creative fields", "communication", "helping others"]
        },
        "strengths_and_challenges": {
            "strengths": ["adaptability", "creativity", "intuition"],
            "challenges": ["overthinking", "sensitivity", "indecision"]
        },
        "life_path": {
            "overview": "A path of creative self-expression and helping others",
            "key_development_areas": ["self-confidence", "decision-making", "emotional balance"]
        }
}'''
        
        analysis = parse_personality_response(valid_json_response)
        
        # Verify the analysis was parsed correctly
        self.assertEqual(analysis.overview, "A creative and intuitive individual with strong communication skills")
        self.assertIn("creative", analysis.personality_traits.key_traits)
        self.assertIn("sensitive", analysis.emotional_nature.emotional_characteristics)


class TestRelationshipContext(unittest.TestCase):
    """Test relationship analysis context building and parsing."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.user_chart = self._create_user_chart()
        self.partner_chart = self._create_partner_chart()
    
    def _create_user_chart(self):
        """Create mock user chart."""
        return AstrologicalChart(
            planets={
                'sun': PlanetPosition(name='Sun', sign='Aries', house=1, degree=10.0),
                'moon': PlanetPosition(name='Moon', sign='Libra', house=7, degree=15.0)
            },
            houses={},
            sun_sign=SignData(name='Aries', element='Fire', modality='Cardinal', ruling_planet='Mars'),
            moon_sign=SignData(name='Libra', element='Air', modality='Cardinal', ruling_planet='Venus'),
            ascendant=SignData(name='Aries', element='Fire', modality='Cardinal', ruling_planet='Mars'),
        )
    
    def _create_partner_chart(self):
        """Create mock partner chart."""
        return AstrologicalChart(
            planets={
                'sun': PlanetPosition(name='Sun', sign='Cancer', house=4, degree=20.0),
                'moon': PlanetPosition(name='Moon', sign='Capricorn', house=10, degree=25.0)
            },
            houses={},
            sun_sign=SignData(name='Cancer', element='Water', modality='Cardinal', ruling_planet='Moon'),
            moon_sign=SignData(name='Capricorn', element='Earth', modality='Cardinal', ruling_planet='Saturn'),
            ascendant=SignData(name='Cancer', element='Water', modality='Cardinal', ruling_planet='Moon'),
        )
    
    def test_build_relationship_context_structure(self):
        """Test relationship context structure."""
        from kerykeion.kr_types.kr_models import RelationshipScoreModel
        
        # Create mock score object
        mock_score = RelationshipScoreModel(
            score_value=75,
            score_description="Important",
            is_destiny_sign=True,
            aspects=[],
            subjects=[]  # Required field
        )
        
        system, user = build_relationship_context(
            chart_1=self.user_chart,
            chart_2=self.partner_chart,
            score=mock_score,
            relationship_type="romantic"
        )
        
        self.assertIsInstance(system, str)
        self.assertIsInstance(user, str)
        self.assertIn('relationship', system.lower())
        self.assertIn('compatibility', system.lower())
    
    def test_parse_relationship_response_valid(self):
        """Test parsing valid relationship response."""
        valid_json_response = '''"score": 85,
        "overview": "A highly compatible relationship with strong potential",
        "compatibility_level": "Excellent",
        "destiny_signs": "Fire and Water create dynamic balance",
        "relationship_aspects": [
            "Strong emotional connection",
            "Complementary energies",
            "Good communication potential"
        ],
        "strengths": [
            "Deep emotional understanding",
            "Balanced give and take",
            "Shared values"
        ],
        "challenges": [
            "Different communication styles",
            "Need for patience",
            "Balancing independence"
        ],
        "areas_for_growth": [
            "Improve listening skills",
            "Practice patience",
            "Develop trust"
        ]
}'''
        
        analysis = parse_relationship_response(valid_json_response)
        
        # Verify the analysis was parsed correctly
        self.assertEqual(analysis.score, 85)
        self.assertEqual(analysis.overview, "A highly compatible relationship with strong potential")
        self.assertEqual(analysis.compatibility_level, "Excellent")
        self.assertIn("Strong emotional connection", analysis.relationship_aspects)


class TestChatContext(unittest.TestCase):
    """Test chat context building."""
    
    def test_build_chat_context_structure(self):
        """Test chat context returns proper structure."""
        profile_data = {
            "birth_data": "Sun in Leo, Moon in Cancer...",
            "personality_analysis": "You are creative and nurturing...",
            "relationships": "Your relationships show...",
            "recent_horoscopes": "Recent cosmic influences..."
        }
        
        system, user = build_chat_context(profile_data)
        
        self.assertIsInstance(system, str)
        self.assertIsInstance(user, str)
        self.assertIn('astrological', system.lower())
    
    def test_build_chat_context_empty_profile(self):
        """Test chat context with empty profile."""
        empty_profile = {}
        
        system, user = build_chat_context(empty_profile)
        
        self.assertIsInstance(system, str)
        self.assertIsInstance(user, str)


class TestCompositeContext(unittest.TestCase):
    """Test composite chart context building and parsing."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_composite_chart = self._create_mock_composite_chart()
    
    def _create_mock_composite_chart(self):
        """Create mock composite chart."""
        return AstrologicalChart(
            planets={
                'sun': PlanetPosition(name='Sun', sign='Virgo', house=6, degree=12.0)
            },
            houses={},
            sun_sign=SignData(name='Virgo', element='Earth', modality='Mutable', ruling_planet='Mercury'),
            moon_sign=SignData(name='Virgo', element='Earth', modality='Mutable', ruling_planet='Mercury'),
            ascendant=SignData(name='Virgo', element='Earth', modality='Mutable', ruling_planet='Mercury'),
        )
    
    def test_build_composite_context_structure(self):
        """Test composite context structure."""
        system, user = build_composite_context(self.mock_composite_chart)
        
        self.assertIsInstance(system, str)
        self.assertIsInstance(user, str)
        self.assertIn('composite', system.lower())
    
    def test_parse_composite_response_valid(self):
        """Test parsing valid composite response."""
        valid_json_response = '''"overview": "A relationship built on mutual understanding and shared goals",
        "relationship_identity": {
            "core_identity": ["harmonious", "growth-oriented", "supportive"]
        },
        "emotional_dynamics": {
            "emotional_patterns": ["deep connection", "empathetic understanding", "emotional stability"]
        },
        "communication_style": {
            "communication_patterns": ["open dialogue", "thoughtful expression", "active listening"]
        },
        "love_expression": {
            "love_patterns": ["affectionate", "romantic", "devoted"]
        },
        "public_image": {
            "external_perception": ["admired couple", "role models", "inspiring"]
        },
        "strengths_and_challenges": {
            "strengths": ["mutual respect", "shared vision", "emotional maturity"],
            "challenges": ["perfectionism", "high expectations", "work-life balance"]
        },
        "long_term_potential": {
            "future_outlook": ["lasting commitment", "continued growth", "legacy building"]
        }
}'''
        
        analysis = parse_composite_response(valid_json_response)
        
        # Verify the analysis was parsed correctly
        self.assertEqual(analysis.overview, "A relationship built on mutual understanding and shared goals")
        self.assertIn("harmonious", analysis.relationship_identity["core_identity"])
        self.assertIn("mutual respect", analysis.strengths_and_challenges["strengths"])


class TestDailyHoroscopeContext(unittest.TestCase):
    """Test daily horoscope context building."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.birth_data = BirthData(
            birth_date='1990-06-15',
            birth_time='12:00',
            latitude=40.7128,
            longitude=-74.0060
        )
        
        self.mock_transit = DailyTransit(
            date=datetime(2024, 1, 15),
            aspects=[],
            retrograding=["Mercury"]
        )
    
    def test_build_horoscope_context_structure(self):
        """Test daily horoscope context structure."""
        from models import DailyTransitChange, TransitChanges, RetrogradeChanges
        
        # Create a mock birth chart
        mock_birth_chart = AstrologicalChart(
            planets={
                'sun': PlanetPosition(name='Sun', sign='Gemini', house=3, degree=12.5),
                'moon': PlanetPosition(name='Moon', sign='Pisces', house=12, degree=8.3)
            },
            houses={},
            sun_sign=SignData(name='Gemini', element='Air', modality='Mutable', ruling_planet='Mercury'),
            moon_sign=SignData(name='Pisces', element='Water', modality='Mutable', ruling_planet='Neptune'),
            ascendant=SignData(name='Gemini', element='Air', modality='Mutable', ruling_planet='Mercury'),
            light_svg="<svg>mock chart</svg>",
            dark_svg='<svg>mock chart</svg>'
        )
        
        # Create mock transit changes
        mock_transit_changes = DailyTransitChange(
            date='2024-01-15',
            aspects=TransitChanges(began=[], ended=[]),
            retrogrades=RetrogradeChanges(began=[], ended=[])
        )
        
        system, user = build_horoscope_context(
            birth_chart=mock_birth_chart,
            transit_changes=mock_transit_changes
        )
        
        self.assertIsInstance(system, str)
        self.assertIsInstance(user, str)
        self.assertIn('horoscope', system.lower())
        self.assertIn('astrological', system.lower())


if __name__ == '__main__':
    unittest.main()