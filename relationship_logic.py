"""Relationship analysis logic using Kerykeion library."""

from kerykeion import AstrologicalSubject, RelationshipScore
from typing import Dict, List, Tuple
import traceback
from models import BirthData, RelationshipScoreResponse
from config import get_logger
from datetime import datetime

logger = get_logger(__name__)

def create_astrological_subject(birth_data: BirthData, name: str = "Subject") -> AstrologicalSubject:
    """Create an AstrologicalSubject from birth data."""
    try:
        # Import here to avoid circular imports
        from astrology import get_timezone_from_coordinates
        
        # Parse birth date and time
        birth_datetime = datetime.fromisoformat(birth_data.birthDate)
        birth_time_parts = birth_data.birthTime.split(':')
        hour = int(birth_time_parts[0])
        minute = int(birth_time_parts[1])
        
        # Get timezone from coordinates
        timezone_str = get_timezone_from_coordinates(birth_data.latitude, birth_data.longitude)
        
        subject = AstrologicalSubject(
            name=name,
            year=birth_datetime.year,
            month=birth_datetime.month,
            day=birth_datetime.day,
            hour=hour,
            minute=minute,
            lng=birth_data.longitude,
            lat=birth_data.latitude,
            tz_str=timezone_str  # Use timezone detected from coordinates
        )
        
        return subject
        
    except Exception as e:
        logger.error(f"Error creating astrological subject: {e}")
        raise ValueError(f"Invalid birth data: {e}")

def calculate_relationship_score(person1_birth_data: BirthData, person2_birth_data: BirthData) -> int:
    """Calculate relationship score using Kerykeion's RelationshipScore (Discepolo method)."""
    try:
        # Create astrological subjects
        person1 = create_astrological_subject(person1_birth_data, "Person1")
        person2 = create_astrological_subject(person2_birth_data, "Person2")
        
        # Calculate relationship score using Kerykeion's implementation
        relationship_score = RelationshipScore(person1, person2)
        
        # Get the total score
        total_score = relationship_score.score
        
        logger.debug(f"Calculated relationship score: {total_score}")
        return total_score
        
    except Exception as e:
        logger.error(f"Error calculating relationship score: {e}")
        logger.error(traceback.format_exc())
        raise ValueError(f"Failed to calculate relationship score: {e}")

def get_compatibility_level(score: int) -> str:
    """Get compatibility level based on Discepolo method ranges."""
    if score <= 5:
        return "Minimal relationship"
    elif score <= 10:
        return "Medium relationship"
    elif score <= 15:
        return "Important relationship"
    elif score <= 20:
        return "Very important relationship"
    elif score <= 35:
        return "Exceptional relationship"
    else:
        return "Rare Exceptional relationship"

def analyze_relationship_details(person1_birth_data: BirthData, person2_birth_data: BirthData) -> Dict:
    """Analyze detailed relationship aspects beyond just the score."""
    try:
        # Create astrological subjects
        person1 = create_astrological_subject(person1_birth_data, "Person1")
        person2 = create_astrological_subject(person2_birth_data, "Person2")
        
        # Use the convert_subject_to_chart method to properly extract chart data
        from astrology import convert_subject_to_chart
        chart1 = convert_subject_to_chart(person1, with_svg=False)
        chart2 = convert_subject_to_chart(person2, with_svg=False)
        
        # Calculate relationship score object for detailed analysis
        relationship_score = RelationshipScore(person1, person2)
        
        # Extract detailed information using the properly converted charts
        details = {
            "sun_sign_person1": chart1.sunSign.name,
            "sun_sign_person2": chart2.sunSign.name,
            "moon_sign_person1": chart1.moonSign.name,
            "moon_sign_person2": chart2.moonSign.name,
            "ascendant_person1": chart1.ascendant.name,
            "ascendant_person2": chart2.ascendant.name,
            "total_score": relationship_score.score,
            "relevant_aspects": getattr(relationship_score, 'relevant_aspects', [])
        }
        
        return details
        
    except Exception as e:
        logger.error(f"Error analyzing relationship details: {e}")
        logger.error(traceback.format_exc())
        return {
            "error": str(e),
            "total_score": 0,
            "relevant_aspects": []
        }

def generate_relationship_interpretation(score: int, compatibility_level: str, details: Dict) -> Tuple[str, List[str], List[str], str]:
    """Generate interpretation text for the relationship analysis."""
    
    # Main explanation
    explanation = f"""Based on the Discepolo method of synastry analysis, this relationship scores {score} points, 
    indicating a {compatibility_level.lower()}. This scoring system evaluates key astrological connections between 
    birth charts, including Sun-Sun aspects, Sun-Moon conjunctions, and other significant planetary interactions."""
    
    # Strengths based on score
    strengths = []
    if score >= 15:
        strengths.extend([
            "Strong astrological compatibility",
            "Significant karmic connection",
            "Natural understanding between partners"
        ])
    elif score >= 10:
        strengths.extend([
            "Good basic compatibility",
            "Meaningful connection potential",
            "Shared values and interests likely"
        ])
    elif score >= 5:
        strengths.extend([
            "Some areas of compatibility",
            "Growth through differences",
            "Complementary qualities"
        ])
    else:
        strengths.extend([
            "Opportunity for personal growth",
            "Learning through contrast",
            "Independent paths that can coexist"
        ])
    
    # Challenges based on score
    challenges = []
    if score < 10:
        challenges.extend([
            "May require more effort to understand each other",
            "Different life approaches",
            "Need for conscious communication"
        ])
    elif score < 15:
        challenges.extend([
            "Occasional misunderstandings",
            "Different emotional needs",
            "Balancing individual goals"
        ])
    else:
        challenges.extend([
            "Managing high expectations",
            "Maintaining independence in closeness",
            "Avoiding codependency"
        ])
    
    # Advice based on compatibility level
    if score >= 20:
        advice = "This is a rare and exceptional connection. Focus on maintaining balance, respecting each other's individuality, and using this strong bond to support mutual growth."
    elif score >= 15:
        advice = "You have a very strong connection. Nurture this relationship with open communication, shared goals, and appreciation for your natural compatibility."
    elif score >= 10:
        advice = "This relationship has solid potential. Work on understanding each other's differences, communicate openly, and focus on building trust and shared experiences."
    elif score >= 5:
        advice = "While compatibility may require effort, this relationship can grow through patience, understanding, and acceptance of differences. Focus on what you appreciate about each other."
    else:
        advice = "This relationship may be challenging but can offer valuable lessons. Approach with realistic expectations, clear communication, and respect for individual paths."
    
    return explanation, strengths, challenges, advice