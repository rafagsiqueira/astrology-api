from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
from typing import Dict, List, Optional, Any
from kerykeion import AstrologicalSubject, KerykeionChartSVG
from timezonefinder import TimezoneFinder
import json
import logging
import traceback
import os
import anthropic
from dotenv import load_dotenv
from datetime import datetime, timezone
import solarsystem
import base64

# Load environment variables from .env file
load_dotenv()

app = FastAPI(title="Cosmic Guru API", version="1.0.0")

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize timezone finder
tf = TimezoneFinder()

# Initialize Claude API client
claude_client = None
try:
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if api_key:
        claude_client = anthropic.Anthropic(api_key=api_key)
        logger.info("Claude API client initialized successfully")
    else:
        logger.warning("ANTHROPIC_API_KEY environment variable not set - personality analysis will be disabled")
except Exception as e:
    logger.error(f"Failed to initialize Claude API client: {e}")
    claude_client = None

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
    theme: Optional[str] = "light"  # "light", "dark"

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

# Personality Analysis Models
class PersonalityTrait(BaseModel):
    name: str
    description: str
    strength: int  # 1-10 scale

class PersonalityAnalysis(BaseModel):
    overview: str
    strengths: List[PersonalityTrait]
    challenges: List[PersonalityTrait]
    relationships: str
    career: str
    lifePath: str

class AnalysisRequest(BaseModel):
    chart: AstrologicalChart
    analysisType: Optional[str] = "comprehensive"  # "comprehensive", "quick", "specific"
    focusAreas: Optional[List[str]] = None  # ["personality", "career", "relationships", "spirituality"]

# Current Planetary Positions Models
class CurrentPlanetPosition(BaseModel):
    name: str
    longitude: float
    latitude: float
    distance: float  # Distance from Earth
    sign: str
    house: Optional[int] = None  # House based on user's chart
    isRetrograde: bool

class TransitAspect(BaseModel):
    transitPlanet: str
    natalPlanet: str
    aspectType: str
    orb: float
    isExact: bool

class CurrentPlanetaryData(BaseModel):
    timestamp: str
    planets: Dict[str, CurrentPlanetPosition]
    moonPhase: str
    transitAspects: List[TransitAspect]

class ChatMessage(BaseModel):
    message: str
    chart: Dict[str, Any]  # User's birth chart
    chatHistory: Optional[List[str]] = None

class ChatResponse(BaseModel):
    response: str
    currentPlanetaryData: CurrentPlanetaryData

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
        
        # Generate SVG chart with theme support
        logger.debug(f"Generating SVG chart with theme: {birth_data.theme}")
        
        # Map theme names to Kerykeion theme options
        # Only include themes that are confirmed to work
        theme_mapping = {
            "light": None,  # Default theme (no theme parameter)
            "dark": "dark",
        }
        
        kerykeion_theme = theme_mapping.get(birth_data.theme, None)
        logger.debug(f"Using Kerykeion theme: {kerykeion_theme}")
        
        # Create chart with or without theme
        try:
            if kerykeion_theme is None:
                chart_svg = KerykeionChartSVG(subject)
            else:
                chart_svg = KerykeionChartSVG(subject, theme=kerykeion_theme)
        except Exception as theme_error:
            logger.warning(f"Failed to create chart with theme '{kerykeion_theme}': {theme_error}")
            logger.info("Falling back to default theme")
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

@app.post("/api/analyze-personality", response_model=PersonalityAnalysis)
async def analyze_personality(analysis_request: AnalysisRequest):
    """Analyze personality based on astrological chart using Claude AI"""
    logger.debug(f"Received personality analysis request for analysis type: {analysis_request.analysisType}")
    
    if claude_client is None:
        raise HTTPException(
            status_code=503, 
            detail="Personality analysis service unavailable - Claude API not configured"
        )
    
    try:
        # Extract key astrological data for analysis
        chart = analysis_request.chart
        chart_summary = _create_chart_summary(chart)
        
        # Create analysis prompt based on request type
        prompt = _create_analysis_prompt(chart_summary, analysis_request)
        
        logger.debug("Sending request to Claude API...")
        
        # Call Claude API
        response = claude_client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=2000,
            temperature=0.7,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        
        # Parse Claude's response
        analysis_text = response.content[0].text
        logger.debug("Received response from Claude API")
        
        # Parse the response into structured data
        parsed_analysis = _parse_claude_response(analysis_text)
        
        return parsed_analysis
        
    except anthropic.APIError as e:
        logger.error(f"Claude API error: {e}")
        raise HTTPException(status_code=503, detail=f"AI analysis service error: {str(e)}")
    except Exception as e:
        logger.error(f"Exception occurred during personality analysis: {str(e)}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error analyzing personality: {str(e)}")

def _create_chart_summary(chart: AstrologicalChart) -> str:
    """Create a concise summary of the astrological chart for AI analysis"""
    summary = f"""Astrological Chart Summary:

Big Three:
- Sun Sign: {chart.sunSign.name} ({chart.sunSign.element} {chart.sunSign.modality})
- Moon Sign: {chart.moonSign.name} ({chart.moonSign.element} {chart.moonSign.modality})
- Ascendant: {chart.ascendant.name} ({chart.ascendant.element} {chart.ascendant.modality})

Planetary Positions:"""
    
    for planet_name, planet in chart.planets.items():
        summary += f"\n- {planet_name}: {planet.sign} in House {planet.house}"
        if planet.isRetrograde:
            summary += " (Retrograde)"
    
    # Add house information
    summary += "\n\nHouse Cusps:"
    for house in chart.houses.values():
        summary += f"\n- House {house.number}: {house.sign}"
    
    return summary

def _create_analysis_prompt(chart_summary: str, request: AnalysisRequest) -> str:
    """Create a detailed prompt for Claude AI based on the analysis request"""
    
    focus_areas = request.focusAreas or ["personality", "relationships", "career", "life_path"]
    analysis_type = request.analysisType or "comprehensive"
    
    prompt = f"""As an expert astrologer, please provide a {analysis_type} personality analysis based on this birth chart. Focus on the following areas: {', '.join(focus_areas)}.

{chart_summary}

Please provide your analysis in the following JSON format (respond with valid JSON only):

{{
    "overview": "A comprehensive 2-3 sentence overview of the person's core personality",
    "strengths": [
        {{"name": "Strength Name", "description": "Detailed description", "strength": 8}},
        {{"name": "Another Strength", "description": "Detailed description", "strength": 7}}
    ],
    "challenges": [
        {{"name": "Challenge Name", "description": "How to work with this challenge", "strength": 6}},
        {{"name": "Another Challenge", "description": "Growth opportunity", "strength": 5}}
    ],
    "relationships": "2-3 sentences about relationship patterns and compatibility",
    "career": "2-3 sentences about career strengths and ideal work environments",
    "lifePath": "2-3 sentences about life purpose and spiritual growth direction"
}}

Provide insightful, specific, and actionable guidance. Use strength ratings from 1-10 where 10 is very strong. Focus on empowering and constructive insights."""

    return prompt

def _parse_claude_response(response_text: str) -> PersonalityAnalysis:
    """Parse Claude's JSON response into PersonalityAnalysis model"""
    try:
        # Clean up the response text to ensure it's valid JSON
        response_text = response_text.strip()
        if response_text.startswith('```json'):
            response_text = response_text[7:]
        if response_text.endswith('```'):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        # Parse JSON response
        data = json.loads(response_text)
        
        # Convert to PersonalityAnalysis model
        strengths = [PersonalityTrait(**trait) for trait in data.get('strengths', [])]
        challenges = [PersonalityTrait(**trait) for trait in data.get('challenges', [])]
        
        return PersonalityAnalysis(
            overview=data.get('overview', ''),
            strengths=strengths,
            challenges=challenges,
            relationships=data.get('relationships', ''),
            career=data.get('career', ''),
            lifePath=data.get('lifePath', '')
        )
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Claude response as JSON: {e}")
        logger.error(f"Raw response: {response_text}")
        
        # Fallback: create a simple analysis from the raw text
        return PersonalityAnalysis(
            overview=response_text[:500] + "..." if len(response_text) > 500 else response_text,
            strengths=[],
            challenges=[],
            relationships="Analysis parsing failed - please try again.",
            career="Analysis parsing failed - please try again.",
            lifePath="Analysis parsing failed - please try again."
        )
    except Exception as e:
        logger.error(f"Error parsing Claude response: {e}")
        raise HTTPException(status_code=500, detail="Failed to parse AI analysis response")

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

def get_current_planetary_data() -> CurrentPlanetaryData:
    """Get current planetary positions using solarsystem library"""
    logger.debug("Getting current planetary positions...")
    
    try:
        # Get current time
        now = datetime.now(timezone.utc)
        timestamp = now.isoformat()
        
        current_planets = {}
        
        try:
            # Create Geocentric object for current time
            G = solarsystem.Geocentric(
                year=now.year, 
                month=now.month, 
                day=now.day, 
                hour=now.hour, 
                minute=now.minute,
                UT=0,  # Universal Time offset 
                dst=0   # Daylight saving time
            )
            
            # Coordinates for Moon calculation
            longitude_coord = 0  # Greenwich longitude
            latitude_coord = 51.5  # Greenwich latitude
            
            # Get all planetary positions
            planets_data = G.planets  # This is a list, not a method
            object_names = G.objectnames()  # This is a method that returns list of names
            
            logger.debug(f"Retrieved {len(planets_data)} planets: {object_names}")
            
            # Process each planet
            for i, (planet_name, planet_coords) in enumerate(zip(object_names, planets_data)):
                # Skip objects we don't want to include
                if planet_name.lower() in ['ceres', 'chiron', 'eris']:
                    continue
                
                # Extract coordinates - the format appears to be (x, y, z) in astronomical units
                # We need to convert to longitude/latitude
                x, y, z = planet_coords
                
                # Convert cartesian to polar coordinates for longitude
                import math
                longitude = math.degrees(math.atan2(y, x))
                if longitude < 0:
                    longitude += 360  # Normalize to 0-360
                
                # Calculate distance
                distance = math.sqrt(x*x + y*y + z*z)
                
                # For simplicity, set latitude to 0 for now (ecliptic latitude)
                latitude = 0.0
                
                # Convert longitude to astrological sign
                sign = _longitude_to_sign(longitude)
                
                # Check if retrograde (simplified logic)
                is_retrograde = _is_planet_retrograde(planet_name.lower(), {'longitude': longitude})
                
                current_planets[planet_name] = CurrentPlanetPosition(
                    name=planet_name,
                    longitude=longitude,
                    latitude=latitude,
                    distance=distance,
                    sign=sign,
                    house=None,  # Will be calculated based on user's chart
                    isRetrograde=is_retrograde
                )
            
            # Get Moon position using dedicated Moon class
            try:
                moon = solarsystem.Moon(
                    year=now.year, 
                    month=now.month, 
                    day=now.day, 
                    hour=now.hour, 
                    minute=now.minute,
                    UT=0, 
                    dst=0, 
                    longtitude=longitude_coord,  # Note: spelled with 't' in this library
                    latitude=latitude_coord, 
                    topographic=True
                )
                moon_position = moon.position()
                
                current_planets['Moon'] = CurrentPlanetPosition(
                    name='Moon',
                    longitude=moon_position[0],  # longitude
                    latitude=moon_position[1],   # latitude
                    distance=moon_position[2],   # distance
                    sign=_longitude_to_sign(moon_position[0]),
                    house=None,
                    isRetrograde=False  # Moon never retrograde
                )
            except Exception as e:
                logger.warning(f"Could not get Moon data: {e}")
                
        except Exception as e:
            logger.error(f"Error getting planetary data from solarsystem: {e}")
            # Create default data for main planets if library fails
            default_planets = ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto']
            for planet_name in default_planets:
                current_planets[planet_name] = CurrentPlanetPosition(
                    name=planet_name,
                    longitude=0.0,
                    latitude=0.0,
                    distance=0.0,
                    sign="Ari",
                    house=None,
                    isRetrograde=False
                )
        
        # Get moon phase (simplified)
        moon_phase = _get_moon_phase(now)
        
        # Transit aspects will be calculated later with user's chart
        transit_aspects = []
        
        return CurrentPlanetaryData(
            timestamp=timestamp,
            planets=current_planets,
            moonPhase=moon_phase,
            transitAspects=transit_aspects
        )
        
    except Exception as e:
        logger.error(f"Error getting current planetary data: {e}")
        # Return empty data structure on error
        return CurrentPlanetaryData(
            timestamp=datetime.now(timezone.utc).isoformat(),
            planets={},
            moonPhase="Unknown",
            transitAspects=[]
        )

def _longitude_to_sign(longitude: float) -> str:
    """Convert longitude degrees to astrological sign"""
    # Each sign is 30 degrees
    signs = ['Ari', 'Tau', 'Gem', 'Can', 'Leo', 'Vir', 
             'Lib', 'Sco', 'Sag', 'Cap', 'Aqu', 'Pis']
    
    # Normalize longitude to 0-360 range
    longitude = longitude % 360
    sign_index = int(longitude // 30)
    
    return signs[sign_index] if 0 <= sign_index < 12 else 'Ari'

def _is_planet_retrograde(planet_name: str, planet_data: dict) -> bool:
    """Simple retrograde detection logic"""
    # This is a simplified implementation
    # In reality, retrograde motion requires comparing positions over time
    # For now, we'll use some basic heuristics
    
    # Mercury retrogrades ~3-4 times per year
    if planet_name.lower() == 'mercury':
        # Simplified: assume retrograde 20% of the time
        longitude = planet_data.get('longitude', 0)
        return (int(longitude) % 5) == 0
    
    # Venus retrogrades ~18 months apart
    if planet_name.lower() == 'venus':
        longitude = planet_data.get('longitude', 0)
        return (int(longitude) % 7) == 0
    
    # Outer planets retrograde more frequently
    if planet_name.lower() in ['mars', 'jupiter', 'saturn', 'uranus', 'neptune', 'pluto']:
        longitude = planet_data.get('longitude', 0)
        return (int(longitude) % 3) == 0
    
    return False

def _get_moon_phase(date_time: datetime) -> str:
    """Get current moon phase"""
    # Simplified moon phase calculation
    # In production, you'd want more accurate lunar calculations
    day_of_month = date_time.day
    
    if day_of_month <= 2 or day_of_month >= 29:
        return "New Moon"
    elif 3 <= day_of_month <= 9:
        return "Waxing Crescent"
    elif 10 <= day_of_month <= 16:
        return "Full Moon"
    elif 17 <= day_of_month <= 23:
        return "Waning Gibbous"
    else:
        return "Waning Crescent"

@app.post("/api/chat", response_model=ChatResponse)
async def chat_with_guru(chat_message: ChatMessage):
    """Chat with the astrological guru using birth chart and current planetary data"""
    logger.debug(f"Received chat message: {chat_message.message[:50]}...")
    
    if claude_client is None:
        raise HTTPException(
            status_code=503, 
            detail="Chat service unavailable - Claude API not configured"
        )
    
    try:
        # Get current planetary data
        current_planetary_data = get_current_planetary_data()
        
        # Create comprehensive context from birth chart
        birth_chart_context = _create_birth_chart_context(chat_message.chart)
        
        # Create current planetary context
        current_planetary_context = _create_current_planetary_context(current_planetary_data)
        
        # Create chat prompt with full astrological context
        prompt = _create_chat_prompt(
            chat_message.message,
            birth_chart_context,
            current_planetary_context,
            chat_message.chatHistory
        )
        
        logger.debug("Sending chat request to Claude API...")
        
        # Call Claude API with comprehensive astrological context
        response = claude_client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=1500,
            temperature=0.8,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        
        # Extract Claude's response
        chat_response = response.content[0].text
        logger.debug("Received chat response from Claude API")
        
        return ChatResponse(
            response=chat_response,
            currentPlanetaryData=current_planetary_data
        )
        
    except anthropic.APIError as e:
        logger.error(f"Claude API error in chat: {e}")
        raise HTTPException(status_code=503, detail=f"AI chat service error: {str(e)}")
    except Exception as e:
        logger.error(f"Exception occurred during chat: {str(e)}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error in chat service: {str(e)}")

def _create_birth_chart_context(chart: Dict[str, Any]) -> str:
    """Create comprehensive birth chart context for the chat"""
    context = "User's Birth Chart Analysis:\n\n"
    
    # Extract basic chart information
    if 'sunSign' in chart:
        sun_sign = chart['sunSign']
        context += f"Sun Sign: {sun_sign.get('name', 'Unknown')} ({sun_sign.get('element', 'Unknown')} {sun_sign.get('modality', 'Unknown')})\n"
    
    if 'moonSign' in chart:
        moon_sign = chart['moonSign']
        context += f"Moon Sign: {moon_sign.get('name', 'Unknown')} ({moon_sign.get('element', 'Unknown')} {moon_sign.get('modality', 'Unknown')})\n"
    
    if 'ascendant' in chart:
        ascendant = chart['ascendant']
        context += f"Ascendant: {ascendant.get('name', 'Unknown')} ({ascendant.get('element', 'Unknown')} {ascendant.get('modality', 'Unknown')})\n"
    
    # Add planetary positions
    if 'planets' in chart:
        context += "\nPlanetary Positions:\n"
        for planet_name, planet_data in chart['planets'].items():
            retrograde_status = " (Retrograde)" if planet_data.get('isRetrograde', False) else ""
            context += f"- {planet_name}: {planet_data.get('sign', 'Unknown')} in House {planet_data.get('house', 'Unknown')}{retrograde_status}\n"
    
    # Add house information
    if 'houses' in chart:
        context += "\nHouse Cusps:\n"
        for house_num, house_data in chart['houses'].items():
            context += f"- House {house_data.get('number', house_num)}: {house_data.get('sign', 'Unknown')}\n"
    
    return context

def _create_current_planetary_context(current_data: CurrentPlanetaryData) -> str:
    """Create current planetary context for the chat"""
    context = f"Current Planetary Positions (as of {current_data.timestamp}):\n\n"
    
    # Add current planetary positions
    for planet_name, planet_data in current_data.planets.items():
        retrograde_status = " (Retrograde)" if planet_data.isRetrograde else ""
        context += f"- {planet_name}: {planet_data.sign} at {planet_data.longitude:.1f}°{retrograde_status}\n"
    
    # Add moon phase
    context += f"\nMoon Phase: {current_data.moonPhase}\n"
    
    # Add any significant transits
    if current_data.transitAspects:
        context += "\nSignificant Transits:\n"
        for aspect in current_data.transitAspects:
            context += f"- {aspect.transitPlanet} {aspect.aspectType} {aspect.natalPlanet} (Orb: {aspect.orb:.1f}°)\n"
    
    return context

def _create_chat_prompt(message: str, birth_chart_context: str, current_planetary_context: str, chat_history: List[str] = None) -> str:
    """Create comprehensive chat prompt with astrological context"""
    
    prompt = f"""You are an experienced and insightful astrological guru. You have deep knowledge of astrology, planetary influences, and how they affect individuals based on their birth charts. You provide thoughtful, personalized guidance that combines the user's natal chart with current planetary positions.

{birth_chart_context}

{current_planetary_context}

Instructions:
1. Always consider both the user's birth chart and current planetary positions in your response
2. Look for significant transits, especially when current planets aspect the user's natal planets
3. Pay special attention to Mercury retrograde periods and their effects on the user's Mercury sign
4. Consider how current planetary alignments might affect the user's Sun, Moon, or Ascendant signs
5. Provide practical, actionable advice that's grounded in astrological principles
6. Be warm, supportive, and encouraging while being honest about challenges
7. Keep responses conversational and accessible (avoid overly technical jargon)
8. If asked about timing, reference current planetary movements and upcoming transits

Chat History:
{chr(10).join(chat_history or [])}

User's Question: {message}

Please provide a thoughtful, personalized response that integrates their birth chart with current planetary influences:"""
    
    return prompt

@app.post("/api/chat-audio", response_model=ChatResponse)
async def chat_with_guru_audio(
    audio: UploadFile = File(...),
    chart: str = Form(...),
    chatHistory: Optional[str] = Form(None)
):
    """Chat with the astrological guru using audio input"""
    logger.debug(f"Received audio chat request")
    
    if claude_client is None:
        raise HTTPException(
            status_code=503, 
            detail="Chat service unavailable - Claude API not configured"
        )
    
    try:
        # Read audio file
        audio_content = await audio.read()
        
        # Parse chart data
        import json
        chart_data = json.loads(chart)
        chat_history_list = json.loads(chatHistory) if chatHistory else None
        
        # Get current planetary data
        current_planetary_data = get_current_planetary_data()
        
        # Create comprehensive context from birth chart
        birth_chart_context = _create_birth_chart_context(chart_data)
        
        # Create current planetary context
        current_planetary_context = _create_current_planetary_context(current_planetary_data)
        
        # Create base prompt for audio processing
        base_prompt = f"""You are an experienced and insightful astrological guru. The user has sent you an audio message. First, transcribe what they said, then provide a thoughtful, personalized response that integrates their birth chart with current planetary influences.

{birth_chart_context}

{current_planetary_context}

Instructions:
1. Transcribe the user's audio message clearly
2. Always consider both the user's birth chart and current planetary positions in your response
3. Look for significant transits, especially when current planets aspect the user's natal planets
4. Pay special attention to Mercury retrograde periods and their effects on the user's Mercury sign
5. Consider how current planetary alignments might affect the user's Sun, Moon, or Ascendant signs
6. Provide practical, actionable advice that's grounded in astrological principles
7. Be warm, supportive, and encouraging while being honest about challenges
8. Keep responses conversational and accessible (avoid overly technical jargon)
9. If asked about timing, reference current planetary movements and upcoming transits

Chat History:
{chr(10).join(chat_history_list or [])}

Please transcribe the audio message and then provide your astrological guidance:"""
        
        logger.debug("Sending audio chat request to Claude API...")
        
        # Call Claude API with audio content
        response = claude_client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=1500,
            temperature=0.8,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": base_prompt
                        },
                        {
                            "type": "audio",
                            "source": {
                                "type": "base64",
                                "media_type": f"audio/{audio.content_type.split('/')[-1]}" if audio.content_type else "audio/wav",
                                "data": base64.b64encode(audio_content).decode('utf-8')
                            }
                        }
                    ]
                }
            ]
        )
        
        # Extract Claude's response
        chat_response = response.content[0].text
        logger.debug("Received audio chat response from Claude API")
        
        return ChatResponse(
            response=chat_response,
            currentPlanetaryData=current_planetary_data
        )
        
    except anthropic.APIError as e:
        logger.error(f"Claude API error in audio chat: {e}")
        raise HTTPException(status_code=503, detail=f"AI chat service error: {str(e)}")
    except Exception as e:
        logger.error(f"Exception occurred during audio chat: {str(e)}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error in audio chat service: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)