"""Core astrology function tests - organized and comprehensive."""

import pytest
import unittest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from astrology import (
    get_element, get_modality, get_ruler, 
    create_cosmiclogical_subject, generate_birth_chart,
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


class TestCosmiclogyHelpers(unittest.TestCase):
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
    
    def test_create_cosmiclogical_subject_valid_data(self):
        """Test creating cosmiclogical subject with valid data."""
        subject = create_cosmiclogical_subject(self.birth_data)
        
        self.assertIsNotNone(subject)
        # Check if subject has basic attributes (implementation details may vary)
        self.assertTrue(hasattr(subject, 'year'))
        self.assertTrue(hasattr(subject, 'month'))
        self.assertTrue(hasattr(subject, 'day'))
    
    @patch('astrology.logger')
    def test_create_cosmiclogical_subject_invalid_data(self, mock_logger):
        """Test creating cosmiclogical subject with invalid data."""
        invalid_data = BirthData(
            birth_date='invalid-date',  # Invalid date format
            birth_time='25:70',  # Invalid time format
            latitude=200,  # Invalid latitude
            longitude=200   # Invalid longitude
        )
        
        with self.assertRaises(Exception):
            create_cosmiclogical_subject(invalid_data)


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
        
        # Should have changes for day 1, day 2 and day 3
        self.assertEqual(len(result), 3)
        
        # Find changes by date
        day1_changes = next(c for c in result if c.date == "2024-01-01")
        day2_changes = next(c for c in result if c.date == "2024-01-02")
        day3_changes = next(c for c in result if c.date == "2024-01-03")
        
        # Check day 1 changes (first day - all began)
        self.assertEqual(len(day1_changes.aspects.began), 0)  # Empty aspects
        self.assertEqual(len(day1_changes.aspects.ended), 0)
        self.assertEqual(day1_changes.retrogrades.began, ["Mercury"])
        self.assertEqual(day1_changes.retrogrades.ended, [])
        
        # Check day 2 changes
        self.assertEqual(len(day2_changes.aspects.began), 0)  # No aspects
        self.assertEqual(len(day2_changes.aspects.ended), 0)
        self.assertEqual(day2_changes.retrogrades.began, ["Venus"])  # Venus retrograde began
        self.assertEqual(day2_changes.retrogrades.ended, [])
        
        # Check day 3 changes
        self.assertEqual(len(day3_changes.aspects.began), 0)
        self.assertEqual(len(day3_changes.aspects.ended), 0)  # No aspects
        self.assertEqual(day3_changes.retrogrades.began, [])
        self.assertEqual(day3_changes.retrogrades.ended, ["Mercury"])  # Mercury retrograde ended
    
    def test_diff_transits_no_changes(self):
        """Test diff_transits when there are no changes between days."""
        # Create identical transits
        identical_transit = DailyTransit(
            date=datetime(2024, 1, 2),
            aspects=[],  # Empty aspects
            retrograding=["Mercury"]
        )
        
        result = diff_transits([self.transit_day1, identical_transit])
        
        # Should only have the first day (all began)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].date, "2024-01-01")  # Only the first day is included


if __name__ == '__main__':
    unittest.main()