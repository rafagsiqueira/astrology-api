from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
from typing import Dict, List, Optional
from kerykeion import AstrologicalSubject, KerykeionChartSVG
from timezonefinder import TimezoneFinder
import json
import logging
import traceback

app = FastAPI(title="Cosmic Guru API", version="1.0.0")

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize timezone finder
tf = TimezoneFinder()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your Flutter app's domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class BirthData(BaseModel):
    birthDate: str  # ISO format date
    birthTime: str  # HH:MM format
    latitude: float
    longitude: float
    cityName: str
    countryName: str
    timezone: str

class PlanetPosition(BaseModel):
    name: str
    longitude: float
    sign: str
    house: int
    isRetrograde: bool

class HousePosition(BaseModel):
    number: int
    cusp: float
    sign: str

class AspectData(BaseModel):
    planet1: str
    planet2: str
    aspectType: str
    orb: float
    isApplying: bool

class SignData(BaseModel):
    name: str
    element: str
    modality: str
    ruler: str

class AstrologicalChart(BaseModel):
    planets: Dict[str, PlanetPosition]
    houses: Dict[str, HousePosition]
    aspects: List[AspectData]
    sunSign: SignData
    moonSign: SignData
    ascendant: SignData
    chartSvg: str

@app.get("/")
async def root():
    return {"message": "Cosmic Guru API is running"}

@app.post("/api/generate-chart", response_model=AstrologicalChart)
async def generate_chart(birth_data: BirthData):
    logger.debug(f"Received birth data: {birth_data}")
    try:
        # Parse birth date and time
        logger.debug(f"Parsing birth date: {birth_data.birthDate}")
        birth_date = datetime.fromisoformat(birth_data.birthDate.replace('Z', '+00:00'))
        logger.debug(f"Parsed birth date: {birth_date}")
        
        logger.debug(f"Parsing birth time: {birth_data.birthTime}")
        birth_time_parts = birth_data.birthTime.split(':')
        hour = int(birth_time_parts[0])
        minute = int(birth_time_parts[1])
        logger.debug(f"Parsed time - hour: {hour}, minute: {minute}")
        
        # Get timezone from coordinates
        logger.debug(f"Looking up timezone for coordinates: {birth_data.latitude}, {birth_data.longitude}")
        timezone_str = tf.timezone_at(lat=birth_data.latitude, lng=birth_data.longitude)
        if not timezone_str:
            # Fallback to UTC if timezone lookup fails
            timezone_str = 'UTC'
            logger.warning(f"Could not determine timezone for coordinates {birth_data.latitude}, {birth_data.longitude}, using UTC")
        else:
            logger.debug(f"Found timezone: {timezone_str}")
        
        # Create astrological subject
        logger.debug("Creating AstrologicalSubject...")
        subject = AstrologicalSubject(
            name="User",
            year=birth_date.year,
            month=birth_date.month,
            day=birth_date.day,
            hour=hour,
            minute=minute,
            lat=birth_data.latitude,
            lng=birth_data.longitude,
            tz_str=timezone_str,
            city=birth_data.cityName,
            nation=birth_data.countryName
        )
        logger.debug("AstrologicalSubject created successfully")
        
        # Extract planetary positions
        logger.debug("Extracting planetary positions...")
        planets = {}
        planet_names = ["sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn", "uranus", "neptune", "pluto"]
        
        for planet_key in planet_names:
            if hasattr(subject, planet_key):
                planet_data = getattr(subject, planet_key)
                # Convert house name to number
                house_name = planet_data.house
                house_number = 1  # default
                if house_name:
                    house_mapping = {
                        'First_House': 1, 'Second_House': 2, 'Third_House': 3, 'Fourth_House': 4,
                        'Fifth_House': 5, 'Sixth_House': 6, 'Seventh_House': 7, 'Eighth_House': 8,
                        'Ninth_House': 9, 'Tenth_House': 10, 'Eleventh_House': 11, 'Twelfth_House': 12
                    }
                    house_number = house_mapping.get(house_name, 1)
                
                planets[planet_key.capitalize()] = PlanetPosition(
                    name=planet_key.capitalize(),
                    longitude=float(planet_data.abs_pos),
                    sign=str(planet_data.sign),
                    house=house_number,
                    isRetrograde=bool(planet_data.retrograde)
                )
        
        # Extract house positions
        houses = {}
        house_names = ['first_house', 'second_house', 'third_house', 'fourth_house', 
                      'fifth_house', 'sixth_house', 'seventh_house', 'eighth_house',
                      'ninth_house', 'tenth_house', 'eleventh_house', 'twelfth_house']
        
        for i, house_name in enumerate(house_names, 1):
            if hasattr(subject, house_name):
                house_data = getattr(subject, house_name)
                houses[str(i)] = HousePosition(
                    number=i,
                    cusp=float(house_data.abs_pos),
                    sign=str(house_data.sign)
                )
        
        # Extract aspects (simplified - for now just empty list)
        aspects = []
        
        # Get sign data
        sun_sign = SignData(
            name=subject.sun.sign,
            element=get_element(subject.sun.sign),
            modality=get_modality(subject.sun.sign),
            ruler=get_ruler(subject.sun.sign)
        )
        
        moon_sign = SignData(
            name=subject.moon.sign,
            element=get_element(subject.moon.sign),
            modality=get_modality(subject.moon.sign),
            ruler=get_ruler(subject.moon.sign)
        )
        
        ascendant_sign = SignData(
            name=subject.first_house.sign,
            element=get_element(subject.first_house.sign),
            modality=get_modality(subject.first_house.sign),
            ruler=get_ruler(subject.first_house.sign)
        )
        
        # Generate SVG chart
        chart_svg = KerykeionChartSVG(subject)
        svg_content = chart_svg.makeTemplate()
        
        return AstrologicalChart(
            planets=planets,
            houses=houses,
            aspects=aspects,
            sunSign=sun_sign,
            moonSign=moon_sign,
            ascendant=ascendant_sign,
            chartSvg=svg_content
        )
        
    except Exception as e:
        logger.error(f"Exception occurred while generating chart: {str(e)}")
        logger.error(f"Exception type: {type(e).__name__}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error generating chart: {str(e)}")

def get_element(sign: str) -> str:
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
    modalities = {
        'Ari': 'Cardinal', 'Can': 'Cardinal', 'Lib': 'Cardinal', 'Cap': 'Cardinal',
        'Tau': 'Fixed', 'Leo': 'Fixed', 'Sco': 'Fixed', 'Aqu': 'Fixed',
        'Gem': 'Mutable', 'Vir': 'Mutable', 'Sag': 'Mutable', 'Pis': 'Mutable',
        # Full names as backup
        'Aries': 'Cardinal', 'Cancer': 'Cardinal', 'Libra': 'Cardinal', 'Capricorn': 'Cardinal',
        'Taurus': 'Fixed', 'Scorpio': 'Fixed', 'Aquarius': 'Fixed',
        'Gemini': 'Mutable', 'Virgo': 'Mutable', 'Sagittarius': 'Mutable', 'Pisces': 'Mutable'
    }
    return modalities.get(sign, 'Unknown')

def get_ruler(sign: str) -> str:
    rulers = {
        'Ari': 'Mars', 'Tau': 'Venus', 'Gem': 'Mercury', 'Can': 'Moon',
        'Leo': 'Sun', 'Vir': 'Mercury', 'Lib': 'Venus', 'Sco': 'Pluto',
        'Sag': 'Jupiter', 'Cap': 'Saturn', 'Aqu': 'Uranus', 'Pis': 'Neptune',
        # Full names as backup
        'Aries': 'Mars', 'Taurus': 'Venus', 'Gemini': 'Mercury', 'Cancer': 'Moon',
        'Virgo': 'Mercury', 'Libra': 'Venus', 'Scorpio': 'Pluto',
        'Sagittarius': 'Jupiter', 'Capricorn': 'Saturn', 'Aquarius': 'Uranus', 'Pisces': 'Neptune'
    }
    return rulers.get(sign, 'Unknown')

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)