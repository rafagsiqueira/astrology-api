"""Astrology module for chart generation."""

from datetime import datetime
from typing import List, Dict, Any, Optional, Union, Tuple
from datetime import date, timedelta
from kerykeion import AstrologicalSubject, KerykeionChartSVG
import pytz
from timezonefinder import TimezoneFinder
from config import get_logger
from models import (
    BirthData, CurrentLocation, HoroscopePeriod, PlanetPosition, HousePosition, 
    AstrologicalChart, SignData
)
from cloud_storage import upload_chart_to_storage, get_chart_from_storage

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
    birth_data: BirthData,
    name: str = "User",
) -> AstrologicalSubject:
    """Create an AstrologicalSubject from location and birth timestamp.
    
    Args:
        birth_data: BirthData object containing date, time, and coordinates
        
    Returns:
        AstrologicalSubject instance
    """

    timezone = get_timezone_from_coordinates(
        latitude=birth_data.latitude,
        longitude=birth_data.longitude
    )

    tz = pytz.timezone(timezone)
    
    # Convert timestamp to timezone-aware datetime in the specified timezone
    # This ensures we get the correct local time for the birth location
    date = datetime.fromisoformat(f"{birth_data.birth_date} {birth_data.birth_time}")
    logger.debug(f"Creating AstrologicalSubject with timezone: {timezone}, local_date: {date}")
    
    # Create astrological subject using local time components
    return AstrologicalSubject(
        name=name,
        year=date.year,
        month=date.month,
        day=date.day,
        hour=date.hour,
        minute=date.minute,
        lat=birth_data.latitude,
        lng=birth_data.longitude,
        tz_str=timezone
    )

def generate_transits(current_location: CurrentLocation, period: HoroscopePeriod) -> List[AstrologicalSubject]:
    """Generate AstrologicalSubjects for different time periods based on horoscope type.
    
    Args:
        current_location: Current location for planetary positions
        period: Horoscope period (WEEK, MONTH, YEAR)
        
    Returns:
        List of AstrologicalSubjects for the specified period
    """
    try:        
        current_tz = get_timezone_from_coordinates(current_location.latitude, current_location.longitude)
        tz = pytz.timezone(current_tz)

        today = date.today()
        transits = []

        if period == HoroscopePeriod.WEEK:
            # Generate one AstrologicalSubject for each of the next 7 days
            for i in range(7):
                target_date = today + timedelta(days=i)
                target_datetime = datetime.combine(target_date, datetime.min.time().replace(hour=12))  # Use noon
                
                transit_subject = AstrologicalSubject(
                    name=f"Transit_Day_{i+1}",
                    year=target_datetime.year,
                    month=target_datetime.month,
                    day=target_datetime.day,
                    hour=target_datetime.hour,
                    minute=target_datetime.minute,
                    lat=current_location.latitude,
                    lng=current_location.longitude,
                    tz_str=current_tz
                )
                transits.append(transit_subject)
                
        elif period == HoroscopePeriod.MONTH:
            # Generate one AstrologicalSubject every 5 days for the next month (6 subjects)
            for i in range(0, 30, 5):
                target_date = today + timedelta(days=i)
                target_datetime = datetime.combine(target_date, datetime.min.time().replace(hour=12))  # Use noon
                
                transit_subject = AstrologicalSubject(
                    name=f"Transit_Period_{i//5 + 1}",
                    year=target_datetime.year,
                    month=target_datetime.month,
                    day=target_datetime.day,
                    hour=target_datetime.hour,
                    minute=target_datetime.minute,
                    lat=current_location.latitude,
                    lng=current_location.longitude,
                    tz_str=current_tz
                )
                transits.append(transit_subject)
                
        elif period == HoroscopePeriod.YEAR:
            # Generate one AstrologicalSubject for the 1st day of each month for the next 12 months
            for i in range(12):
                # Calculate the target month/year
                target_month = today.month + i
                target_year = today.year
                
                # Handle year rollover
                while target_month > 12:
                    target_month -= 12
                    target_year += 1
                
                # Use 1st day of the month
                target_date = date(target_year, target_month, 1)
                target_datetime = datetime.combine(target_date, datetime.min.time().replace(hour=12))  # Use noon
                
                transit_subject = AstrologicalSubject(
                    name=f"Transit_Month_{target_month}",
                    year=target_datetime.year,
                    month=target_datetime.month,
                    day=target_datetime.day,
                    hour=target_datetime.hour,
                    minute=target_datetime.minute,
                    lat=current_location.latitude,
                    lng=current_location.longitude,
                    tz_str=current_tz
                )
                transits.append(transit_subject)

        return transits
        
    except Exception as e:
        logger.error(f"Failed to generate transits: {e}")
        return []

def subject_to_chart(subject: AstrologicalSubject, with_svg: bool = True) -> AstrologicalChart:
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
        
        user_subject = create_astrological_subject(
            birth_data=birth_data,
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
        
        return subject_to_chart(subject=user_subject)
        
    except Exception as e:
        logger.error(f"Failed to generate birth chart: {e}")
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