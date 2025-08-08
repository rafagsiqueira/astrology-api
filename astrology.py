"""Astrology module for chart generation."""

from datetime import datetime
from typing import List
from datetime import date, timedelta
from kerykeion import AstrologicalSubject, KerykeionChartSVG
from kerykeion.composite_subject_factory import CompositeSubjectFactory
from kerykeion.kr_types.kr_models import CompositeSubjectModel, TransitMomentModel
from kerykeion.transits_time_range import TransitsTimeRangeFactory
from kerykeion.ephemeris_data import EphemerisDataFactory
import pytz
from timezonefinder import TimezoneFinder
from config import get_logger
from models import (
    BirthData, CurrentLocation, DailyTransit, HoroscopePeriod, PlanetPosition, HousePosition, 
    AstrologicalChart, SignData, CompositeAnalysisRequest
)

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
        tz_str=timezone,
        disable_chiron_and_lilith=True
    )

def generate_transits(birth_data: BirthData, current_location: CurrentLocation, start_date: datetime, period: HoroscopePeriod) -> list[DailyTransit]:
    """Generate AstrologicalSubjects for different time periods based on horoscope type.
    
    Args:
        current_location: Current location for planetary positions
        start_date: datetime value of the day to start calculating transits
        
    Returns:
        TransitsTimeRangeModel object
    """
    subject = create_astrological_subject(birth_data=birth_data)

    end_date = start_date + timedelta(days=1)
    if period == HoroscopePeriod.week:
        end_date = start_date + timedelta(days=7)
    if period == HoroscopePeriod.month:
        #TODO: Will get periods from day 1 to last day of the month of start_date
        raise Exception("Not implemented yet")
    if period == HoroscopePeriod.year:
        #TODO: Will get periods from day 1 to last day of the year of start_date
        raise Exception("Not implemented yet")

    aspects_and_retrograding_planets = []
    
    subjects = []
    current_date = start_date
    while current_date <= end_date:
        birth_data = BirthData(
            birth_date=f"{current_date.year}-{str(current_date.month).zfill(2)}-{str(current_date.day).zfill(2)}",
            birth_time="12:00",
            latitude=current_location.latitude,
            longitude=current_location.longitude
        )
        subjects.append(create_astrological_subject(birth_data=birth_data))
        current_date = current_date + timedelta(days=1)

    transits = TransitsTimeRangeFactory(natal_chart=subject, ephemeris_data_points=subjects)
    transit_moments = transits.get_transit_moments().transits
    aspects_and_retrograding_planets: list[DailyTransit] = []
    for idx, moment in enumerate(transit_moments):
        retrograding_planets = []
        planet_names = ['mercury', 'venus', 'mars', 'jupiter', 'saturn', 'uranus', 'neptune', 'pluto']
        for planet_name in planet_names:
            planet = getattr(subjects[idx], planet_name)
            if hasattr(planet, 'retrograde') and planet.retrograde:
                retrograding_planets.append(planet_name.capitalize())
        aspects_and_retrograding_planets.append(DailyTransit(date=datetime.fromisoformat(moment.date), aspects=moment.aspects, retrograding=retrograding_planets))
    return aspects_and_retrograding_planets

def subject_to_chart(subject: AstrologicalSubject | CompositeSubjectModel, with_svg: bool = True) -> AstrologicalChart:
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
        chart_image_url = None
        
        if with_svg:
            try:
                chart_svg = KerykeionChartSVG(first_obj=subject, chart_type="Natal", theme="dark")
                svg_content = chart_svg.makeWheelOnlyTemplate(minify=True, remove_css_variables=True)
                logger.debug("Chart SVG generated successfully")
            except Exception as svg_error:
                logger.error(f"Failed to generate chart SVG: {svg_error}")
            
            # Upload SVG to cloud storage if available
            if svg_content and svg_content != "<svg><text>Chart generation failed</text></svg>":
                try:
                    from cloud_storage import upload_chart_to_storage
                    chart_image_url = upload_chart_to_storage(svg_content)
                    
                    if chart_image_url:
                        logger.debug(f"Chart uploaded to cloud storage: {chart_image_url}")
                    else:
                        logger.warning("Failed to upload chart to cloud storage")
                except Exception as storage_error:
                    logger.error(f"Error uploading chart to storage: {storage_error}")
        
        return AstrologicalChart(
            planets=planets_dict,
            houses=houses_dict,
            sunSign=sun_sign,
            moonSign=moon_sign,
            ascendant=ascendant_sign,
            chartSvg=svg_content,
            chartImageUrl=chart_image_url
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

        return subject_to_chart(subject=user_subject, with_svg=with_svg)
        
    except Exception as e:
        logger.error(f"Failed to generate birth chart: {e}")
        raise

def generate_composite_chart(request: CompositeAnalysisRequest, with_svg: bool = True) -> AstrologicalChart:
    """Generate a composite chart from two people's birth data using midpoint method."""
    try:
        logger.debug(f"Generating composite chart between two subjects")
        
        # Create AstrologicalSubjects for both people
        person1_subject = create_astrological_subject(
            birth_data=request.person1_birth_data,
            name="Person1"
        )
        
        person2_subject = create_astrological_subject(
            birth_data=request.person2_birth_data,
            name="Person2"
        )
        
        # Create composite subject using midpoint method
        composite_factory = CompositeSubjectFactory(person1_subject, person2_subject)
        composite_subject = composite_factory.get_midpoint_composite_subject_model()
        
        # Convert to AstrologicalChart
        composite_chart = subject_to_chart(subject=composite_subject, with_svg=with_svg)
        
        logger.debug("Composite chart generated successfully")
        return composite_chart
        
    except Exception as e:
        logger.error(f"Failed to generate composite chart: {e}")
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