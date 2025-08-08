#!/usr/bin/env python3
"""Test script to verify the transit generation fix."""

import sys
from datetime import datetime
from models import BirthData, CurrentLocation, HoroscopePeriod
from astrology import generate_transits
from config import get_logger

# Set up logging
logger = get_logger(__name__)

def test_generate_transits():
    """Test the generate_transits function with sample data."""
    print("Testing generate_transits function...")
    
    # Sample birth data (similar to what might cause the error)
    birth_data = BirthData(
        birth_date="1990-01-01",
        birth_time="12:00",
        latitude=40.7128,
        longitude=-74.0060
    )
    
    # Current location (New York)
    current_location = CurrentLocation(
        latitude=40.7128,
        longitude=-74.0060
    )
    
    # Test target date
    target_date = datetime(2024, 8, 8, 12, 0)  # Today
    
    try:
        print(f"Generating transits for {target_date.date()}")
        
        # Test DAY period
        transits = generate_transits(
            birth_data=birth_data,
            current_location=current_location,
            start_date=target_date,
            period=HoroscopePeriod.day
        )
        
        print(f"✅ DAY period: Generated {len(transits)} transits")
        
        if transits:
            for i, transit in enumerate(transits[:3]):  # Show first 3
                print(f"  Transit {i+1}: {transit.date.date()}, {len(transit.aspects)} aspects, {len(transit.retrograding)} retrograde")
        
        # Test WEEK period
        transits_week = generate_transits(
            birth_data=birth_data,
            current_location=current_location,
            start_date=target_date,
            period=HoroscopePeriod.week
        )
        
        print(f"✅ WEEK period: Generated {len(transits_week)} transits")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_edge_cases():
    """Test edge cases that might cause issues."""
    print("\nTesting edge cases...")
    
    # Test with different birth times that might cause issues
    edge_cases = [
        ("1986-01-14", "11:35"),  # User's actual birth data from error
        ("1990-02-29", "00:00"),  # Leap year boundary
        ("2000-12-31", "23:59"),  # Year boundary
    ]
    
    current_location = CurrentLocation(
        latitude=-19.9246634,  # User's actual location from error
        longitude=-43.935406900000004
    )
    
    target_date = datetime(2025, 8, 8, 12, 0)
    
    for birth_date, birth_time in edge_cases:
        try:
            birth_data = BirthData(
                birth_date=birth_date,
                birth_time=birth_time,
                latitude=current_location.latitude,
                longitude=current_location.longitude
            )
            
            transits = generate_transits(
                birth_data=birth_data,
                current_location=current_location,
                start_date=target_date,
                period=HoroscopePeriod.day
            )
            
            print(f"✅ Edge case {birth_date} {birth_time}: {len(transits)} transits")
            
        except Exception as e:
            print(f"❌ Edge case {birth_date} {birth_time} failed: {e}")
            return False
    
    return True

if __name__ == "__main__":
    print("=" * 60)
    print("TESTING TRANSIT GENERATION FIX")
    print("=" * 60)
    
    success = True
    
    # Run tests
    success &= test_generate_transits()
    success &= test_edge_cases()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 ALL TESTS PASSED!")
        sys.exit(0)
    else:
        print("💥 SOME TESTS FAILED!")
        sys.exit(1)