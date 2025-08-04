"""Unit test for build_horoscope_context method."""

import unittest
from datetime import datetime
from models import BirthData, CurrentLocation, HoroscopeRequest, HoroscopePeriod
from contexts import build_horoscope_context

class TestBuildHoroscopeContext(unittest.TestCase):
    """Test cases for build_horoscope_context method."""
    
    def setUp(self):
        """Set up test data."""
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
    
    def test_build_horoscope_context_week(self):
        """Test building horoscope context for weekly horoscope."""
        request = HoroscopeRequest(
            birth_data=self.birth_data,
            current_location=self.current_location,
            horoscope_type=HoroscopePeriod.WEEK
        )
        
        context = build_horoscope_context(request)
        
        print("=== WEEKLY HOROSCOPE CONTEXT ===")
        print(f"Context length: {len(context)} characters")
        print("Context content:")
        print(context)
        print("=" * 50)
        
        # Verify context contains expected elements
        self.assertIn("week", context.lower())
        self.assertIn("astrology_aspects", context)
        self.assertIn("horoscope", context.lower())
        self.assertIsInstance(context, str)
        self.assertGreater(len(context), 100)
    
    def test_build_horoscope_context_month(self):
        """Test building horoscope context for monthly horoscope."""
        request = HoroscopeRequest(
            birth_data=self.birth_data,
            current_location=self.current_location,
            horoscope_type=HoroscopePeriod.MONTH
        )
        
        context = build_horoscope_context(request)
        
        print("\n=== MONTHLY HOROSCOPE CONTEXT ===")
        print(f"Context length: {len(context)} characters")
        print("Context content:")
        print(context)
        print("=" * 50)
        
        # Verify context contains expected elements
        self.assertIn("month", context.lower())
        self.assertIn("astrology_aspects", context)
        self.assertIn("horoscope", context.lower())
        self.assertIsInstance(context, str)
        self.assertGreater(len(context), 100)
    
    def test_build_horoscope_context_year(self):
        """Test building horoscope context for yearly horoscope."""
        request = HoroscopeRequest(
            birth_data=self.birth_data,
            current_location=self.current_location,
            horoscope_type=HoroscopePeriod.YEAR
        )
        
        context = build_horoscope_context(request)
        
        print("\n=== YEARLY HOROSCOPE CONTEXT ===")
        print(f"Context length: {len(context)} characters")
        print("Context content:")
        print(context)
        print("=" * 50)
        
        # Verify context contains expected elements
        self.assertIn("year", context.lower())
        self.assertIn("astrology_aspects", context)
        self.assertIn("horoscope", context.lower())
        self.assertIsInstance(context, str)
        self.assertGreater(len(context), 100)
    
    def test_context_structure(self):
        """Test that the context has the expected structure."""
        request = HoroscopeRequest(
            birth_data=self.birth_data,
            current_location=self.current_location,
            horoscope_type=HoroscopePeriod.WEEK
        )
        
        context = build_horoscope_context(request)
        
        # Check for key structural elements
        self.assertIn("You are an expert astrologer", context)
        self.assertIn("astrology_aspects", context)
        self.assertIn("<horoscope>", context)
        self.assertIn("</horoscope>", context)
        self.assertIn("<overview>", context)
        self.assertIn("<body>", context)
        self.assertIn("<conclusion>", context)
        
        print(f"\n=== CONTEXT STRUCTURE ANALYSIS ===")
        print(f"Contains astrologer role: {'You are an expert astrologer' in context}")
        print(f"Contains astrology_aspects placeholder: {'astrology_aspects' in context}")
        print(f"Contains horoscope tags: {'<horoscope>' in context and '</horoscope>' in context}")
        print(f"Contains structure tags: {'<overview>' in context and '<body>' in context and '<conclusion>' in context}")

if __name__ == "__main__":
    unittest.main()