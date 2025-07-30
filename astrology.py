"""Astrology module for chart generation."""

from datetime import datetime
from typing import List, Dict, Any
from kerykeion import AstrologicalSubject, KerykeionChartSVG
from timezonefinder import TimezoneFinder
from config import get_logger
from models import (
    BirthData, CurrentLocation, PlanetPosition, HousePosition, 
    AstrologicalChart, SignData
)
from zoneinfo import ZoneInfo

logger = get_logger(__name__)

# Initialize timezone finder
tf = TimezoneFinder()

def get_element(sign: str) -> str:
    """Get the element for a zodiac sign."""
    elements = {
        'Ari': 'Fire', 'Leo': 'Fire', 'Sag': 'Fire',
        'Tau': 'Earth', 'Vir': 'Earth', 'Cap': 'Earth',
        'Gem': 'Air', 'Lib': 'Air', 'Aqu': 'Air',
        'Can': 'Water', 'Sco': 'Water', 'Pis': 'Water',
        # Full names as backup
        'Aries': 'Fire', 'Sagittarius': 'Fire',
        'Taurus': 'Earth', 'Virgo': 'Earth', 'Capricorn': 'Earth',
        'Gemini': 'Air', 'Libra': 'Air', 'Aquarius': 'Air',
        'Cancer': 'Water', 'Scorpio': 'Water', 'Pisces': 'Water'
    }
    return elements.get(sign, 'Unknown')

def get_modality(sign: str) -> str:
    """Get the modality for a zodiac sign."""
    modalities = {
        'Ari': 'Cardinal', 'Can': 'Cardinal', 'Lib': 'Cardinal', 'Cap': 'Cardinal',
        'Tau': 'Fixed', 'Leo': 'Fixed', 'Sco': 'Fixed', 'Aqu': 'Fixed',
        'Gem': 'Mutable', 'Vir': 'Mutable', 'Sag': 'Mutable', 'Pis': 'Mutable',
        # Full names as backup
        'Aries': 'Cardinal', 'Cancer': 'Cardinal', 'Libra': 'Cardinal', 'Capricorn': 'Cardinal',
        'Taurus': 'Fixed', 'Leo': 'Fixed', 'Scorpio': 'Fixed', 'Aquarius': 'Fixed',
        'Gemini': 'Mutable', 'Virgo': 'Mutable', 'Sagittarius': 'Mutable', 'Pisces': 'Mutable'
    }
    return modalities.get(sign, 'Unknown')

def get_ruler(sign: str) -> str:
    """Get the ruling planet for a zodiac sign."""
    rulers = {
        'Ari': 'Mars', 'Tau': 'Venus', 'Gem': 'Mercury', 'Can': 'Moon',
        'Leo': 'Sun', 'Vir': 'Mercury', 'Lib': 'Venus', 'Sco': 'Pluto',
        'Sag': 'Jupiter', 'Cap': 'Saturn', 'Aqu': 'Uranus', 'Pis': 'Neptune',
        # Full names as backup
        'Aries': 'Mars', 'Taurus': 'Venus', 'Gemini': 'Mercury', 'Cancer': 'Moon',
        'Leo': 'Sun', 'Virgo': 'Mercury', 'Libra': 'Venus', 'Scorpio': 'Pluto',
        'Sagittarius': 'Jupiter', 'Capricorn': 'Saturn', 'Aquarius': 'Uranus', 'Pisces': 'Neptune'
    }
    return rulers.get(sign, 'Unknown')


def create_astrological_subject(
    latitude: float, 
    longitude: float, 
    birth_timestamp: float,
    timezone: str,
    name: str = "Subject"
) -> AstrologicalSubject:
    """Create an AstrologicalSubject from location and optional birth date.
    
    Args:
        latitude: Latitude coordinate
        longitude: Longitude coordinate  
        birth_date: Birth timestamp
        name: Name for the subject
        
    Returns:
        AstrologicalSubject instance
    """
    
    date = datetime.fromtimestamp(birth_timestamp)
    
    # Create astrological subject
    return AstrologicalSubject(
        name=name,
        year=date.year,
        month=date.month,
        day=date.day,
        hour=date.hour,
        minute=date.minute,
        lat=latitude,
        lng=longitude,
        tz_str=timezone
    )

def generate_transit(user_birth_data: BirthData, current_location: CurrentLocation) -> List[Dict[str, Any]]:
    """Generate transit aspects between user's birth chart and current planetary positions.
    
    Args:
        user_birth_data: User's birth data
        current_location: Current location for planetary positions
        
    Returns:
        List of transit aspects
    """
    try:
        from kerykeion import SynastryAspects
        
        # Generate both subjects
        user_tz = get_timezone_from_coordinates(user_birth_data.latitude, user_birth_data.longitude)
        user_subject = create_astrological_subject(
            latitude=user_birth_data.latitude,
            longitude=user_birth_data.longitude,
            birth_timestamp=user_birth_data.birthTimestamp,
            timezone=user_tz,
            name="User"
        )
        current_tz = get_timezone_from_coordinates(current_location.latitude, current_location.longitude)
        current_subject = create_astrological_subject(
            latitude=current_location.latitude,
            longitude=current_location.longitude,
            birth_timestamp=datetime.now(ZoneInfo(current_tz)).timestamp(),
            timezone=current_tz
        )

        kerykeion_chart = KerykeionChartSVG(
            first_obj=user_subject,
            second_obj=current_subject,
            chart_type="Transit",
            theme="dark",
        )
        
        aspects = SynastryAspects(
            user_subject,
            current_subject,
        ).relevant_aspects
        
        return [aspect.model_dump() for aspect in aspects]
        
    except Exception as e:
        logger.error(f"Failed to generate synastry: {e}")
        return []

def convert_subject_to_chart(subject: AstrologicalSubject, with_svg: bool = True) -> AstrologicalChart:
    """Convert an AstrologicalSubject to an AstrologicalChart."""
    try:
        # Process planets data
        planets_dict = {}
        for planet_name in ['sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn', 'uranus', 'neptune', 'pluto']:
            if hasattr(subject, planet_name):
                planet = getattr(subject, planet_name)
                # Convert house name to number
                house_num = 1  # default
                if hasattr(planet, 'house') and planet.house:
                    house_name = planet.house
                    if isinstance(house_name, str):
                        house_mapping = {
                            'First_House': 1, 'Second_House': 2, 'Third_House': 3,
                            'Fourth_House': 4, 'Fifth_House': 5, 'Sixth_House': 6,
                            'Seventh_House': 7, 'Eighth_House': 8, 'Ninth_House': 9,
                            'Tenth_House': 10, 'Eleventh_House': 11, 'Twelfth_House': 12
                        }
                        house_num = house_mapping.get(house_name, 1)
                    else:
                        house_num = int(house_name)
                
                planets_dict[planet_name.capitalize()] = PlanetPosition(
                    name=planet_name.capitalize(),
                    sign=planet.sign,
                    house=house_num,
                    degree=planet.abs_pos,
                    retrograde=planet.retrograde if hasattr(planet, 'retrograde') else False
                )
        
        # Process houses data using correct attribute names
        houses_dict = {}
        house_names = [
            'first_house', 'second_house', 'third_house', 'fourth_house',
            'fifth_house', 'sixth_house', 'seventh_house', 'eighth_house',
            'ninth_house', 'tenth_house', 'eleventh_house', 'twelfth_house'
        ]
        
        for i, house_name in enumerate(house_names, 1):
            if hasattr(subject, house_name):
                house = getattr(subject, house_name)
                houses_dict[f"house_{i}"] = HousePosition(
                    house=i,
                    sign=house.sign,
                    degree=house.abs_pos
                )
        
        # Create sign data objects
        sun_sign = SignData(
            name=subject.sun.sign,
            element=get_element(subject.sun.sign),
            modality=get_modality(subject.sun.sign),
            ruling_planet=get_ruler(subject.sun.sign)
        )
        
        moon_sign = SignData(
            name=subject.moon.sign,
            element=get_element(subject.moon.sign),
            modality=get_modality(subject.moon.sign),
            ruling_planet=get_ruler(subject.moon.sign)
        )
        
        ascendant_sign = SignData(
            name=subject.first_house.sign,
            element=get_element(subject.first_house.sign),
            modality=get_modality(subject.first_house.sign),
            ruling_planet=get_ruler(subject.first_house.sign)
        )
        
        # Generate SVG if requested
        svg_content = ""
        if with_svg:
            try:
                chart_svg = KerykeionChartSVG(first_obj=subject, chart_type="Natal", theme="dark")
                svg_content = chart_svg.makeWheelOnlyTemplate(minify=True, remove_css_variables=True)
                logger.debug("Chart SVG generated successfully")
            except Exception as svg_error:
                logger.error(f"Failed to generate chart SVG: {svg_error}")
        
        return AstrologicalChart(
            planets=planets_dict,
            houses=houses_dict,
            sunSign=sun_sign,
            moonSign=moon_sign,
            ascendant=ascendant_sign,
            chartSvg=svg_content
        )
        
    except Exception as e:
        logger.error(f"Failed to convert subject to chart: {e}")
        raise

def generate_birth_chart(birth_data: BirthData, with_svg: bool = True) -> AstrologicalChart:
    """Generate a complete astrological chart from birth data."""
    try:
        logger.debug(f"Generating birth chart for coordinates {birth_data.latitude}, {birth_data.longitude}")
        
        # Use the new generate_user_subject method
        # Generate both subjects
        user_tz = get_timezone_from_coordinates(birth_data.latitude, birth_data.longitude)
        user_subject = create_astrological_subject(
            latitude=birth_data.latitude,
            longitude=birth_data.longitude,
            birth_timestamp=birth_data.birthTimestamp,
            timezone=user_tz,
            name="User"
        )

        svg_content = ""
        if with_svg:
            logger.debug("Generating chart SVG...")
            
            chart_svg = KerykeionChartSVG(user_subject, "Natal", theme="dark")
            svg_content = chart_svg.makeWheelOnlyTemplate(minify=True, remove_css_variables=True)
            
            # Check if SVG generation succeeded
            if svg_content is None:
                logger.error("SVG generation returned None")
                svg_content = "<svg><text>Chart generation failed</text></svg>"
        
        return convert_subject_to_chart(subject=user_subject)
        
    except Exception as e:
        logger.error(f"Failed to generate birth chart: {e}")
        raise

def current_chart(current_location: CurrentLocation) -> AstrologicalChart:
    """Get current positions using planetary data."""
    try:
        logger.debug("Getting current planetary positions...")

        current_tz = get_timezone_from_coordinates(current_location.latitude, current_location.longitude)
        current_subject = create_astrological_subject(
            latitude=current_location.latitude,
            longitude=current_location.longitude,
            birth_timestamp=datetime.now(ZoneInfo(current_tz)).timestamp(),
            timezone=current_tz
        )

        return convert_subject_to_chart(subject=current_subject, with_svg=False)
        
    except Exception as e:
        logger.error(f"Failed to get current planetary positions: {e}")
        raise

def get_timezone_from_coordinates(latitude: float, longitude: float) -> str:
    """Get timezone string from latitude/longitude coordinates."""
    try:
        timezone_str = tf.timezone_at(lat=latitude, lng=longitude)
        if timezone_str:
            return timezone_str
        else:
            logger.warning(f"Could not determine timezone for coordinates ({latitude}, {longitude})")
            return "UTC"
    except Exception as e:
        logger.error(f"Error getting timezone: {e}")
        return "UTC"