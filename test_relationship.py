#!/usr/bin/env python3
"""Simple test for relationship analysis functionality."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models import BirthData
from relationship_logic import (
    calculate_relationship_score, 
    get_compatibility_level, 
    analyze_relationship_details,
    generate_relationship_interpretation
)

def test_relationship_analysis():
    """Test relationship analysis with sample birth data."""
    
    # Sample birth data for testing
    person1_birth_data = BirthData(
        birthDate="1990-07-15",
        birthTime="14:30",
        latitude=40.7128,
        longitude=-74.0060
    )
    
    person2_birth_data = BirthData(
        birthDate="1992-03-22",
        birthTime="09:15", 
        latitude=34.0522,
        longitude=-118.2437
    )
    
    try:
        print("Testing relationship analysis...")
        
        # Calculate relationship score
        score = calculate_relationship_score(person1_birth_data, person2_birth_data)
        print(f"Relationship Score: {score}")
        
        # Get compatibility level
        compatibility_level = get_compatibility_level(score)
        print(f"Compatibility Level: {compatibility_level}")
        
        # Get detailed analysis
        details = analyze_relationship_details(person1_birth_data, person2_birth_data)
        print(f"Details: {details}")
        
        # Generate interpretation
        explanation, strengths, challenges, advice = generate_relationship_interpretation(
            score, compatibility_level, details
        )
        print(f"Explanation: {explanation[:100]}...")
        print(f"Strengths: {strengths}")
        print(f"Challenges: {challenges}")
        print(f"Advice: {advice[:100]}...")
        
        print("\n✓ Relationship analysis test completed successfully!")
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_relationship_analysis()