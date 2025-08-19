"""Core astrology function tests - organized and comprehensive."""

import pytest
import unittest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from astrology import (
    get_element, get_modality, get_ruler, 
    create_astrological_subject, generate_birth_chart,
    generate_transits, diff_transits
)
from models import BirthData, CurrentLocation, HoroscopePeriod, DailyTransit

# Create a simple mock aspect class that works with Pydantic validation
class MockAspect:
    """Mock aspect class for testing."""
    def __init__(self, p1_name, p2_name, aspect):
        self.p1_name = p1_name
        self.p2_name = p2_name
        self.aspect = aspect


class TestAstrologyHelpers(unittest.TestCase):
    """Test helper functions for astrology."""
    
    def test_get_element_all_signs(self):
        """Test element mapping for all zodiac signs."""
        fire_signs = ['Ari', 'Leo', 'Sag', 'Aries', 'Sagittarius']
        earth_signs = ['Tau', 'Vir', 'Cap', 'Taurus', 'Virgo', 'Capricorn']
        air_signs = ['Gem', 'Lib', 'Aqu', 'Gemini', 'Libra', 'Aquarius']
        water_signs = ['Can', 'Sco', 'Pis', 'Cancer', 'Scorpio', 'Pisces']
        
        for sign in fire_signs:
            self.assertEqual(get_element(sign), 'Fire')
        for sign in earth_signs:
            self.assertEqual(get_element(sign), 'Earth')
        for sign in air_signs:
            self.assertEqual(get_element(sign), 'Air')
        for sign in water_signs:
            self.assertEqual(get_element(sign), 'Water')
    
    def test_get_element_unknown_sign(self):
        """Test element mapping for unknown signs."""
        self.assertEqual(get_element('Unknown'), 'Unknown')
        self.assertEqual(get_element(''), 'Unknown')
    
    def test_get_modality_all_signs(self):
        """Test modality mapping for all zodiac signs."""
        cardinal_signs = ['Ari', 'Can', 'Lib', 'Cap', 'Aries', 'Cancer', 'Libra', 'Capricorn']
        fixed_signs = ['Tau', 'Leo', 'Sco', 'Aqu', 'Taurus', 'Scorpio', 'Aquarius']
        mutable_signs = ['Gem', 'Vir', 'Sag', 'Pis', 'Gemini', 'Virgo', 'Sagittarius', 'Pisces']
        
        for sign in cardinal_signs:
            self.assertEqual(get_modality(sign), 'Cardinal')
        for sign in fixed_signs:
            self.assertEqual(get_modality(sign), 'Fixed')
        for sign in mutable_signs:
            self.assertEqual(get_modality(sign), 'Mutable')
    
    def test_get_ruler_all_signs(self):
        """Test ruler mapping for all zodiac signs."""
        expected_rulers = {
            'Ari': 'Mars', 'Aries': 'Mars',
            'Tau': 'Venus', 'Taurus': 'Venus',
            'Gem': 'Mercury', 'Gemini': 'Mercury',
            'Can': 'Moon', 'Cancer': 'Moon',
            'Leo': 'Sun',
            'Vir': 'Mercury', 'Virgo': 'Mercury',
            'Lib': 'Venus', 'Libra': 'Venus',
            'Sco': 'Pluto', 'Scorpio': 'Pluto',
            'Sag': 'Jupiter', 'Sagittarius': 'Jupiter',
            'Cap': 'Saturn', 'Capricorn': 'Saturn',
            'Aqu': 'Uranus', 'Aquarius': 'Uranus',
            'Pis': 'Neptune', 'Pisces': 'Neptune'
        }
        
        for sign, expected_ruler in expected_rulers.items():
            self.assertEqual(get_ruler(sign), expected_ruler)


class TestChartGeneration(unittest.TestCase):
    """Test chart generation functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.birth_data = BirthData(
            birth_date='1990-05-15',
            birth_time='10:30',
            latitude=40.7128,
            longitude=-74.0060
        )
    
    def test_create_astrological_subject_valid_data(self):
        """Test creating astrological subject with valid data."""
        subject = create_astrological_subject(self.birth_data)
        
        self.assertIsNotNone(subject)
        # Check if subject has basic attributes (implementation details may vary)
        self.assertTrue(hasattr(subject, 'year'))
        self.assertTrue(hasattr(subject, 'month'))
        self.assertTrue(hasattr(subject, 'day'))
    
    @patch('astrology.logger')
    def test_create_astrological_subject_invalid_coordinates(self, mock_logger):
        """Test creating astrological subject with invalid coordinates."""
        from pydantic import ValidationError
        
        # Test invalid latitude
        with self.assertRaises(ValidationError):
            BirthData(
                birth_date='1990-01-01',
                birth_time='12:00',
                latitude=200,  # Invalid latitude
                longitude=-74.0060
            )
        
        # Test invalid longitude
        with self.assertRaises(ValidationError):
            BirthData(
                birth_date='1990-01-01',
                birth_time='12:00',
                latitude=40.7128,
                longitude=200  # Invalid longitude
            )

    @patch('astrology.logger')
    def test_create_astrological_subject_invalid_datetime_format(self, mock_logger):
        """Test creating astrological subject with invalid date/time format."""
        from unittest.mock import patch
        
        # Create a valid BirthData object but with an invalid date format that will fail in datetime.fromisoformat
        # We need to bypass Pydantic validation by creating the object with valid values first
        birth_data = BirthData(
            birth_date='1990-01-01',
            birth_time='12:00',
            latitude=40.7128,
            longitude=-74.0060
        )
        
        # Then manually set invalid values to test the datetime parsing in create_astrological_subject
        birth_data.birth_date = 'invalid-date'
        birth_data.birth_time = '25:70'
        
        with self.assertRaises(ValueError):
            create_astrological_subject(birth_data)


class TestTransitGeneration(unittest.TestCase):
    """Test transit generation functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.birth_data = BirthData(
            birth_date='1990-05-15',
            birth_time='10:30',
            latitude=40.7128,
            longitude=-74.0060
        )
        
        self.current_location = CurrentLocation(
            latitude=40.7128,
            longitude=-74.0060
        )


class TestDiffTransits(unittest.TestCase):
    """Test diff_transits functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        # For now, focus on retrograde testing since aspects require complex setup
        # Create daily transits with empty aspects to avoid pydantic validation issues
        self.transit_day1 = DailyTransit(
            date=datetime(2024, 1, 1),
            aspects=[],  # Empty for now to avoid AspectModel complexity
            retrograding=["Mercury"]
        )
        
        self.transit_day2 = DailyTransit(
            date=datetime(2024, 1, 2),
            aspects=[],  # Empty for now
            retrograding=["Mercury", "Venus"]
        )
        
        self.transit_day3 = DailyTransit(
            date=datetime(2024, 1, 3),
            aspects=[],  # Empty for now
            retrograding=["Venus"]
        )
    
    def test_diff_transits_empty_list(self):
        """Test diff_transits with empty list."""
        result = diff_transits([])
        self.assertEqual(result, [])
    
    def test_diff_transits_single_day(self):
        """Test diff_transits with single day."""
        result = diff_transits([self.transit_day1])
        
        self.assertEqual(len(result), 1)
        
        day_change = result[0]
        self.assertEqual(day_change.date, "2024-01-01")
        self.assertEqual(len(day_change.aspects.began), 0)  # Empty aspects
        self.assertEqual(len(day_change.aspects.ended), 0)
        self.assertEqual(day_change.retrogrades.began, ["Mercury"])
        self.assertEqual(day_change.retrogrades.ended, [])
    
    def test_diff_transits_multiple_days(self):
        """Test diff_transits with multiple days showing changes."""
        result = diff_transits([self.transit_day1, self.transit_day2, self.transit_day3])
        
        # Should have changes for day 2
        self.assertEqual(len(result), 1)
        
        # Find changes by date
        day2_changes = next(c for c in result if c.date == "2024-01-02")
        
        # Check day 2 changes
        self.assertEqual(len(day2_changes.aspects.began), 0)  # No aspects
        self.assertEqual(len(day2_changes.aspects.ended), 0)
        self.assertEqual(day2_changes.retrogrades.began, ["Venus"])  # Venus retrograde began
        self.assertEqual(day2_changes.retrogrades.ended, [])
    
    def test_diff_transits_no_changes(self):
        """Test diff_transits when there are no changes between days."""
        # Create identical transits
        identical_transit = DailyTransit(
            date=datetime(2024, 1, 2),
            aspects=[],  # Empty aspects
            retrograding=["Mercury"]
        )
        
        result = diff_transits([self.transit_day1, identical_transit])
        
        # Should have no changes
        self.assertEqual(len(result), 0)


if __name__ == '__main__':
    unittest.main()