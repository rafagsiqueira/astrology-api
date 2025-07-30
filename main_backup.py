from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
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
import asyncio
import firebase_admin
from firebase_admin import credentials, auth, firestore
from functools import wraps
import xml.etree.ElementTree as ET
import re

# Load environment variables from .env file
load_dotenv()

# Configure logging first
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Firebase Admin SDK
firebase_app = None
try:
    # Check if Firebase Admin is already initialized
    if not firebase_admin._apps:
        # For development, use Application Default Credentials
        # In production, you should use a service account key file
        firebase_app = firebase_admin.initialize_app()
        logger.info("Firebase Admin SDK initialized successfully")
    else:
        firebase_app = firebase_admin.get_app()
        logger.info("Firebase Admin SDK already initialized")
except Exception as e:
    logger.error(f"Failed to initialize Firebase Admin SDK: {e}")
    logger.warning("Authentication features will be disabled")

# Initialize Firestore
db = None
try:
    if firebase_app:
        # Initialize Firestore client (using default database for now)
        # TODO: Multi-database support requires Firebase Admin SDK 7.0+
        database_id = os.getenv('FIRESTORE_DATABASE_ID')
        db = firestore.client()
        if database_id:
            logger.info(f"Firestore client initialized (note: using default database, not '{database_id}' - requires SDK upgrade)")
        else:
            logger.info("Firestore client initialized with default database")
    else:
        logger.warning("Firestore disabled - Firebase Admin SDK not initialized")
except Exception as e:
    logger.error(f"Failed to initialize Firestore: {e}")
    logger.warning("User profiles and database features will be disabled")

app = FastAPI(title="Cosmic Guru API", version="1.0.0")

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

# Authentication dependencies and middleware
async def verify_firebase_token(authorization: str = Header(None)):
    """Verify Firebase ID token and return user info"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header format")
    
    token = authorization.split("Bearer ")[1]
    
    try:
        # Verify the Firebase ID token
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except auth.InvalidIdTokenError:
        raise HTTPException(status_code=401, detail="Invalid Firebase ID token")
    except auth.ExpiredIdTokenError:
        raise HTTPException(status_code=401, detail="Expired Firebase ID token")
    except Exception as e:
        logger.error(f"Firebase token verification error: {e}")
        raise HTTPException(status_code=401, detail="Authentication failed")

async def require_authenticated_user(user_info: dict = Depends(verify_firebase_token)):
    """Dependency that requires any authenticated user (including anonymous)"""
    return user_info

async def require_non_anonymous_user(user_info: dict = Depends(verify_firebase_token)):
    """Dependency that requires a non-anonymous authenticated user"""
    # Check if user is anonymous
    firebase_sign_in_provider = user_info.get('firebase', {}).get('sign_in_provider')
    is_anonymous = firebase_sign_in_provider == 'anonymous'
    
    if is_anonymous:
        raise HTTPException(
            status_code=403, 
            detail="This feature requires full authentication. Please sign in with Google, Apple, or phone number."
        )
    
    return user_info

# Pydantic models
class BirthData(BaseModel):
    birthDate: str  # ISO format date
    birthTime: str  # HH:MM format
    latitude: float
    longitude: float
    cityName: str
    countryName: str
    timezone: str
    theme: Optional[str] = "dark"  # "light", "dark" - default to dark

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

# User Profile Models
class UserProfile(BaseModel):
    user_id: str
    email: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    birth_data: Optional[Dict[str, Any]] = None
    personality_analysis: Optional[Dict[str, Any]] = None
    astrology_chart: Optional[Dict[str, Any]] = None
    preferences: Optional[Dict[str, Any]] = None

class ProfileCreationRequest(BaseModel):
    birth_data: Dict[str, Any]  # BirthData as dict
    generate_analysis: Optional[bool] = True

# User Profile Service Functions
async def create_user_profile(user_id: str, email: Optional[str] = None, birth_data: Optional[Dict[str, Any]] = None) -> UserProfile:
    """Create a new user profile in Firestore"""
    if not db:
        raise HTTPException(status_code=503, detail="Database service unavailable")
    
    try:
        now = datetime.now(timezone.utc)
        
        profile_data = {
            'user_id': user_id,
            'email': email,
            'created_at': now,
            'updated_at': now,
            'birth_data': birth_data,
            'personality_analysis': None,
            'astrology_chart': None,
            'preferences': {}
        }
        
        # Create profile document in Firestore
        doc_ref = db.collection('user_profiles').document(user_id)
        doc_ref.set(profile_data)
        
        logger.info(f"Created user profile for user_id: {user_id}")
        return UserProfile(**profile_data)
        
    except Exception as e:
        logger.error(f"Failed to create user profile for {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to create user profile")

async def get_user_profile(user_id: str) -> Optional[UserProfile]:
    """Get user profile from Firestore"""
    if not db:
        return None
    
    try:
        doc_ref = db.collection('user_profiles').document(user_id)
        doc = doc_ref.get()
        
        if doc.exists:
            data = doc.to_dict()
            return UserProfile(**data)
        return None
        
    except Exception as e:
        logger.error(f"Failed to get user profile for {user_id}: {e}")
        return None

async def update_user_profile(user_id: str, updates: Dict[str, Any]) -> bool:
    """Update user profile in Firestore"""
    if not db:
        return False
    
    try:
        updates['updated_at'] = datetime.now(timezone.utc)
        
        doc_ref = db.collection('user_profiles').document(user_id)
        doc_ref.update(updates)
        
        logger.info(f"Updated user profile for user_id: {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to update user profile for {user_id}: {e}")
        return False

async def store_personality_analysis(user_id: str, birth_data: Dict[str, Any], analysis: Dict[str, Any], chart: Dict[str, Any]) -> bool:
    """Store personality analysis and chart data for a user"""
    if not db:
        return False
    
    try:
        updates = {
            'birth_data': birth_data,
            'personality_analysis': analysis,
            'astrology_chart': chart,
            'updated_at': datetime.now(timezone.utc)
        }
        
        return await update_user_profile(user_id, updates)
        
    except Exception as e:
        logger.error(f"Failed to store personality analysis for {user_id}: {e}")
        return False

async def get_or_create_user_profile(user_info: dict) -> UserProfile:
    """Get existing user profile or create new one"""
    user_id = user_info.get('user_id')
    email = user_info.get('email')
    
    # Try to get existing profile
    profile = await get_user_profile(user_id)
    
    if profile:
        # Update email if it's new or changed
        if email and profile.email != email:
            await update_user_profile(user_id, {'email': email})
            profile.email = email
        return profile
    
    # Create new profile
    return await create_user_profile(user_id, email)

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
        
        # Extract aspects
        aspects = _calculate_aspects(planets)
        
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
            "light": "light",
            "dark": "dark",
        }
        
        # Default to dark theme if no theme specified
        theme = getattr(birth_data, 'theme', 'dark')
        kerykeion_theme = theme_mapping.get(theme, "dark")
        logger.debug(f"Using theme: {theme} -> Kerykeion theme: {kerykeion_theme}")
        
        # Generate chart with specified theme
        if kerykeion_theme == "dark":
            chart_svg = KerykeionChartSVG(subject, theme="dark")
        else:
            chart_svg = KerykeionChartSVG(subject)
        
        svg_content = chart_svg.makeTemplate()
        
        # Clean SVG for Flutter compatibility
        processed_svg = clean_svg_for_flutter(svg_content)
        
        # Debug: Save both original and processed SVG
        try:
            with open('debug_chart_original.svg', 'w') as f:
                f.write(svg_content)
            with open('debug_chart_processed.svg', 'w') as f:
                f.write(processed_svg)
            logger.debug(f"Saved original SVG ({len(svg_content)} chars) and processed SVG ({len(processed_svg)} chars)")
        except Exception as e:
            logger.warning(f"Failed to save debug SVGs: {e}")
        
        return AstrologicalChart(
            planets=planets,
            houses=houses,
            aspects=aspects,
            sunSign=sun_sign,
            moonSign=moon_sign,
            ascendant=ascendant_sign,
            chartSvg=processed_svg
        )
        
    except Exception as e:
        logger.error(f"Exception occurred while generating chart: {str(e)}")
        logger.error(f"Exception type: {type(e).__name__}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error generating chart: {str(e)}")

@app.post("/api/create-profile", response_model=UserProfile)
async def create_profile_with_analysis(
    profile_request: ProfileCreationRequest,
    user_info: dict = Depends(require_non_anonymous_user)
):
    """Create user profile and generate personality analysis for newly authenticated users"""
    logger.debug(f"Creating profile for user: {user_info.get('user_id')}")
    
    try:
        user_id = user_info.get('user_id')
        email = user_info.get('email')
        
        # Get or create user profile
        profile = await get_or_create_user_profile(user_info)
        
        # If birth data is provided and analysis should be generated
        if profile_request.birth_data and profile_request.generate_analysis:
            try:
                # Parse birth data
                birth_data = BirthData(**profile_request.birth_data)
                
                # Generate astrological chart
                chart_response = await generate_chart(birth_data)
                chart_data = chart_response.__dict__
                
                # Generate personality analysis if Claude is available
                if claude_client is not None:
                    analysis_request = AnalysisRequest(
                        chart=chart_response,
                        analysisType="comprehensive"
                    )
                    
                    personality_analysis = await analyze_personality(analysis_request)
                    analysis_data = personality_analysis.__dict__
                    
                    # Store everything in user profile
                    await store_personality_analysis(
                        user_id, 
                        profile_request.birth_data,
                        analysis_data,
                        chart_data
                    )
                    
                    logger.info(f"Generated and stored personality analysis for user: {user_id}")
                else:
                    # Just store chart data without analysis
                    await store_personality_analysis(
                        user_id,
                        profile_request.birth_data,
                        None,
                        chart_data
                    )
                    logger.info(f"Stored chart data for user: {user_id} (Claude unavailable)")
                
                # Refresh profile to get updated data
                profile = await get_user_profile(user_id)
                
            except Exception as e:
                logger.error(f"Failed to generate analysis for user {user_id}: {e}")
                # Continue without failing - profile is still created
        
        return profile
        
    except HTTPException:
        # Re-raise HTTP exceptions with their original status codes
        raise
    except Exception as e:
        logger.error(f"Failed to create profile for user: {e}")
        raise HTTPException(status_code=500, detail="Failed to create user profile")

@app.get("/api/profile", response_model=UserProfile)
async def get_profile(user_info: dict = Depends(require_authenticated_user)):
    """Get current user's profile"""
    user_id = user_info.get('user_id')
    
    profile = await get_user_profile(user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="User profile not found")
    
    return profile

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

def clean_svg_for_flutter(svg_content: str) -> str:
    """
    SVG cleaning for flutter_svg compatibility.
    1) Replace CSS variables with their actual values
    2) Remove the style section
    3) Remove Houses_And_Planets_Grid node using XML parsing
    4) Remove ns0 namespace from all tags
    """
    try:
        logger.debug("Starting SVG cleaning for flutter_svg...")
        
        # First do CSS variable replacement and style removal using string methods
        cleaned = svg_content
        
        # 1. Extract CSS variable values before removing style section
        css_vars = {}
        style_match = re.search(r'<style[^>]*>(.*?)</style>', cleaned, re.DOTALL)
        if style_match:
            style_content = style_match.group(1)
            # Extract CSS variable definitions like --kerykeion-chart-color-paper-0: #ffffff;
            var_matches = re.findall(r'--([^:]+):\s*([^;]+);', style_content)
            for var_name, var_value in var_matches:
                css_vars[f'--{var_name.strip()}'] = var_value.strip()
        
        logger.debug(f"Extracted {len(css_vars)} CSS variables")
        
        # 2. Replace var() references with actual values (multiple passes for nested variables)
        def replace_var(match):
            var_ref = match.group(0)  # Full var(...) reference
            var_name_match = re.search(r'var\(([^)]+)\)', var_ref)
            if var_name_match:
                var_key = var_name_match.group(1).strip()
                if var_key in css_vars:
                    replacement = css_vars[var_key]
                    return replacement
                else:
                    logger.warning(f"CSS variable {var_key} not found in definitions")
                    return '#000000'  # fallback
            return '#000000'
        
        # Do multiple passes to resolve nested variable references
        max_passes = 5  # Prevent infinite loops
        pass_count = 0
        
        while pass_count < max_passes:
            pass_count += 1
            variables_before = len(re.findall(r'var\([^)]+\)', cleaned))
            
            if variables_before == 0:
                logger.debug(f"All variables resolved after {pass_count - 1} passes")
                break
                
            logger.debug(f"Pass {pass_count}: {variables_before} variables to resolve")
            cleaned = re.sub(r'var\([^)]+\)', replace_var, cleaned)
            
            variables_after = len(re.findall(r'var\([^)]+\)', cleaned))
            logger.debug(f"Pass {pass_count}: {variables_after} variables remaining")
            
            # If no progress made, break to avoid infinite loop
            if variables_after == variables_before:
                logger.debug(f"No progress made in pass {pass_count}, stopping")
                break
        
        # 3. Remove the entire style section
        cleaned = re.sub(r'<style[^>]*>.*?</style>', '', cleaned, flags=re.DOTALL)
        
        # 4. Use XML parsing to safely remove Houses_And_Planets_Grid node
        try:
            # Parse the SVG as XML
            root = ET.fromstring(cleaned)
            
            # Find and remove unwanted elements using XML parsing
            # Search for elements with kr:node attribute regardless of namespace prefix
            removed_count = 0
            nodes_to_remove = ['Houses_And_Planets_Grid', 'Main_Text', 'Aspect_Grid', 'Lunar_Phase']
            
            for node_name in nodes_to_remove:
                elements_to_remove = []
                
                # Iterate through all elements and check their attributes
                for elem in root.iter():
                    for attr_name, attr_value in elem.attrib.items():
                        # Check if this is a kr:node attribute with the target value
                        if attr_name.endswith('node') and attr_value == node_name:
                            elements_to_remove.append(elem)
                            break
                
                # Remove the found elements
                for elem in elements_to_remove:
                    # Find parent by iterating through all elements
                    for potential_parent in root.iter():
                        if elem in list(potential_parent):
                            potential_parent.remove(elem)
                            removed_count += 1
                            break
                            
                logger.debug(f"Removed {len(elements_to_remove)} {node_name} elements")
            
            logger.debug(f"Total removed {removed_count} elements using XML parsing")
            
            # 5. Adjust viewBox to match Main_Content bounds (the actual chart wheel)
            try:
                # Find the Main_Content element (which contains the actual chart wheel)
                main_content_elem = None
                for elem in root.iter():
                    for attr_name, attr_value in elem.attrib.items():
                        if attr_name.endswith('node') and attr_value == 'Main_Content':
                            main_content_elem = elem
                            break
                    if main_content_elem is not None:
                        break
                
                if main_content_elem is not None:
                    # Get the transform offset of Main_Content 
                    transform = main_content_elem.attrib.get('transform', '')
                    content_offset_x, content_offset_y = 0, 0
                    if 'translate(' in transform:
                        translate_match = re.search(r'translate\(([^)]+)\)', transform)
                        if translate_match:
                            translate_vals = translate_match.group(1).split(',')
                            if len(translate_vals) >= 2:
                                content_offset_x = float(translate_vals[0].strip())
                                content_offset_y = float(translate_vals[1].strip())
                    
                    logger.debug(f"Main_Content offset: ({content_offset_x}, {content_offset_y})")
                    
                    # Calculate bounds based on the chart wheel (circles)
                    min_x, min_y, max_x, max_y = float('inf'), float('inf'), float('-inf'), float('-inf')
                    
                    # Find the Full_Wheel element and get its additional transform
                    full_wheel_offset_x, full_wheel_offset_y = 0, 0
                    for elem in main_content_elem.iter():
                        for attr_name, attr_value in elem.attrib.items():
                            if attr_name.endswith('node') and attr_value == 'Full_Wheel':
                                fw_transform = elem.attrib.get('transform', '')
                                if 'translate(' in fw_transform:
                                    translate_match = re.search(r'translate\(([^)]+)\)', fw_transform)
                                    if translate_match:
                                        translate_vals = translate_match.group(1).split(',')
                                        if len(translate_vals) >= 2:
                                            full_wheel_offset_x = float(translate_vals[0].strip())
                                            full_wheel_offset_y = float(translate_vals[1].strip())
                                break
                        if full_wheel_offset_x != 0 or full_wheel_offset_y != 0:
                            break
                    
                    logger.debug(f"Full_Wheel offset: ({full_wheel_offset_x}, {full_wheel_offset_y})")
                    
                    # Look for circle elements (the chart wheel) within Main_Content
                    largest_radius = 0
                    chart_center_x, chart_center_y = 0, 0
                    
                    for elem in main_content_elem.iter():
                        # Look specifically for circles which define the chart wheel
                        if elem.tag == 'circle':
                            cx = elem.attrib.get('cx')
                            cy = elem.attrib.get('cy')
                            r = elem.attrib.get('r')
                            
                            if cx and cy and r:
                                try:
                                    center_x = float(cx)
                                    center_y = float(cy)
                                    radius = float(r)
                                    
                                    # Use the largest circle to define the chart bounds
                                    if radius > largest_radius:
                                        largest_radius = radius
                                        chart_center_x = center_x
                                        chart_center_y = center_y
                                    
                                    logger.debug(f"Found circle: center=({center_x},{center_y}) r={radius}")
                                    
                                except (ValueError, TypeError):
                                    continue
                    
                    # Set a fixed viewBox of 550x550
                    new_viewbox = "60 0 550.0 550.0"
                    root.attrib['viewBox'] = new_viewbox
                    logger.debug(f"Set fixed viewBox to: {new_viewbox}")
                else:
                    logger.debug("Main_Content element not found, setting fixed viewBox anyway")
                    new_viewbox = "60 0 550.0 550.0"
                    root.attrib['viewBox'] = new_viewbox
                    logger.debug(f"Set fixed viewBox to: {new_viewbox}")
                    
            except Exception as viewbox_error:
                logger.warning(f"Failed to adjust viewBox: {viewbox_error}")
                logger.warning("Keeping original viewBox")
            
            # 6. Add black background rectangle as first element
            try:
                # Create a large black rectangle that covers a wide area
                # Use fixed large dimensions that should cover most widget sizes
                bg_rect = ET.Element('rect')
                bg_rect.attrib['x'] = '0'
                bg_rect.attrib['y'] = '0'
                bg_rect.attrib['width'] = '1000'
                bg_rect.attrib['height'] = '1000'
                bg_rect.attrib['fill'] = '#000000'
                
                # Insert the rectangle as the first child (so it's behind everything)
                root.insert(0, bg_rect)
                logger.debug("Added large black background rectangle (0,0 1000x1000)")
                
                # Also remove any background-color from style to avoid conflicts
                current_style = root.attrib.get('style', '')
                if 'background-color:' in current_style:
                    new_style = re.sub(r'background-color:\s*[^;]+;?', '', current_style).strip()
                    if new_style.endswith(';'):
                        new_style = new_style[:-1]
                    if new_style:
                        root.attrib['style'] = new_style
                    else:
                        del root.attrib['style']
                    logger.debug("Removed background-color from style attribute")
            except Exception as bg_error:
                logger.warning(f"Failed to add background rectangle: {bg_error}")
            
            # Convert back to string
            cleaned = ET.tostring(root, encoding='unicode')
            
            # Clean up XML namespace artifacts introduced by ET.tostring()
            # ElementTree changes namespace prefixes, so we need to restore the original format
            
            # Replace ElementTree's generated namespace prefixes with original ones
            cleaned = re.sub(r'<ns0:', '<', cleaned)
            cleaned = re.sub(r'</ns0:', '</', cleaned)
            cleaned = re.sub(r'ns1:', 'kr:', cleaned)  # Restore kr: prefix
            cleaned = re.sub(r'ns2:', 'xlink:', cleaned)  # Restore xlink: prefix
            
            # Clean up namespace declarations - keep only the essential ones
            cleaned = re.sub(r'\s*xmlns:ns[0-9]="[^"]*"', '', cleaned)
            
            # Ensure proper SVG namespace structure
            if 'xmlns=' not in cleaned and '<svg' in cleaned:
                cleaned = cleaned.replace('<svg', 
                    '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:kr="https://www.kerykeion.net/"', 1)
            
        except Exception as xml_error:
            logger.warning(f"XML parsing failed for node removal: {xml_error}")
            logger.warning("Skipping Houses_And_Planets_Grid removal")
            
            # If XML parsing fails, just skip the node removal but continue with other cleaning
            # Remove ns0 namespace from all tags using regex as fallback
            cleaned = re.sub(r'<ns0:', '<', cleaned)
            cleaned = re.sub(r'</ns0:', '</', cleaned)
            cleaned = re.sub(r'\s*xmlns:ns0="[^"]*"', '', cleaned)
        
        # Verify variables were replaced
        remaining_vars = len(re.findall(r'var\([^)]+\)', cleaned))
        logger.debug(f"Final result: {remaining_vars} variables remaining after {pass_count} passes")
        
        if remaining_vars == 0:
            logger.debug("✅ All CSS variables successfully resolved")
        else:
            logger.warning(f"⚠️ {remaining_vars} CSS variables could not be resolved")
        
        logger.debug(f"SVG cleaning completed - reduced from {len(svg_content)} to {len(cleaned)} chars")
        return cleaned
        
    except Exception as e:
        logger.warning(f"Failed to clean SVG: {e}")
        logger.warning("Returning original SVG content")
        return svg_content

def post_process_chart_svg(svg_content: str, adjust_viewbox: bool = False) -> str:
    """
    Post-process the birth chart SVG to remove text elements and keep only the circular chart.
    Uses a more conservative regex-based approach to avoid XML parsing issues.
    
    Args:
        svg_content: The original SVG content
        adjust_viewbox: Whether to adjust the viewBox to focus on chart area (default: False)
    """
    try:
        processed_svg = svg_content
        
        # Remove specific unwanted sections using regex patterns
        # Remove main text section (birth info)
        processed_svg = re.sub(r'<g kr:node=[\'"]Main_Text[\'"]>.*?</g>', '', processed_svg, flags=re.DOTALL)
        
        # Remove lunar phase section
        processed_svg = re.sub(r'<g kr:node=[\'"]Lunar_Phase[\'"][^>]*>.*?</g>', '', processed_svg, flags=re.DOTALL)
        
        # Remove aspect grid (text tables)
        processed_svg = re.sub(r'<g kr:node=[\'"]Aspect_Grid[\'"]>.*?</g>', '', processed_svg, flags=re.DOTALL)
        
        # Remove elements percentages
        processed_svg = re.sub(r'<g kr:node=[\'"]Elements_Percentages[\'"]>.*?</g>', '', processed_svg, flags=re.DOTALL)
        
        # Remove houses and planets grid
        processed_svg = re.sub(r'<g kr:node=[\'"]Houses_And_Planets_Grid[\'"]>.*?</g>', '', processed_svg, flags=re.DOTALL)
        
        # Remove planet grid
        processed_svg = re.sub(r'<g kr:node=[\'"]Planet_Grid[\'"][^>]*>.*?</g>', '', processed_svg, flags=re.DOTALL)
        
        # Remove houses grid
        processed_svg = re.sub(r'<g kr:node=[\'"]Houses_Grid[\'"]>.*?</g>', '', processed_svg, flags=re.DOTALL)
        
        # Remove house number text but keep house lines (more targeted)
        processed_svg = re.sub(r'<g kr:node=[\'"]HouseNumber[\'"]><text[^>]*>.*?</text></g>', '', processed_svg, flags=re.DOTALL)
        
        # Remove any remaining birth data text elements
        processed_svg = re.sub(r'<text[^>]*>[^<]*(?:Info:|Latitude:|Longitude:|Type:|Placidus|Tropical|[0-9]{4}-[0-9]{2}-[0-9]{2}|User|New York)[^<]*</text>', '', processed_svg, flags=re.IGNORECASE)
        
        # Optionally adjust viewBox
        if adjust_viewbox:
            processed_svg = re.sub(r'viewBox=[\'"][0-9\s.]+[\'"]', 'viewBox="20 20 540 540"', processed_svg)
        
        logger.debug("Successfully post-processed chart SVG using regex approach")
        return processed_svg
        
    except Exception as e:
        logger.warning(f"Failed to post-process SVG: {e}")
        logger.warning("Returning original SVG content")
        return svg_content

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

def _get_planetary_speed(planet_name: str) -> float:
    """Get approximate daily motion for planets in degrees per day"""
    # Average daily motion of planets (degrees per day)
    speeds = {
        'Sun': 1.0,       # ~1° per day
        'Moon': 13.2,     # ~13.2° per day (fastest)
        'Mercury': 1.4,   # ~0.4-2.2° per day (varies due to retrograde)
        'Venus': 1.2,     # ~0.7-1.3° per day
        'Mars': 0.5,      # ~0.3-0.7° per day
        'Jupiter': 0.083, # ~5' per day (0.083°)
        'Saturn': 0.033,  # ~2' per day (0.033°)
        'Uranus': 0.012,  # ~42" per day (0.012°)
        'Neptune': 0.006, # ~24" per day (0.006°)
        'Pluto': 0.004,   # ~15" per day (0.004°)
    }
    return speeds.get(planet_name, 0.5)  # Default if planet not found

def _is_aspect_applying(planet1_name: str, planet1_longitude: float, 
                       planet2_name: str, planet2_longitude: float, 
                       target_aspect_degree: float) -> bool:
    """Determine if an aspect is applying (getting closer) or separating"""
    
    # Get planetary speeds
    speed1 = _get_planetary_speed(planet1_name)
    speed2 = _get_planetary_speed(planet2_name)
    
    # Determine which planet is faster
    if speed1 > speed2:
        faster_planet_pos = planet1_longitude
        slower_planet_pos = planet2_longitude
    else:
        faster_planet_pos = planet2_longitude
        slower_planet_pos = planet1_longitude
    
    # Calculate current angular separation
    current_separation = abs(faster_planet_pos - slower_planet_pos)
    if current_separation > 180:
        current_separation = 360 - current_separation
    
    # Calculate what the separation would be if the faster planet moved forward slightly
    future_faster_pos = (faster_planet_pos + 0.1) % 360
    future_separation = abs(future_faster_pos - slower_planet_pos)
    if future_separation > 180:
        future_separation = 360 - future_separation
    
    # For conjunctions (0°), applying means getting closer to 0°
    if target_aspect_degree == 0:
        return future_separation < current_separation
    
    # For other aspects, applying means getting closer to the target degree
    current_diff_from_target = abs(current_separation - target_aspect_degree)
    future_diff_from_target = abs(future_separation - target_aspect_degree)
    
    return future_diff_from_target < current_diff_from_target

def _calculate_aspects(planets: Dict[str, PlanetPosition]) -> List[AspectData]:
    """Calculate aspects between planets based on their longitude positions"""
    aspects = []
    
    # Major aspects and their degrees with orbs (tolerance)
    major_aspects = {
        'Conjunction': {'degree': 0, 'orb': 8},
        'Opposition': {'degree': 180, 'orb': 8},
        'Trine': {'degree': 120, 'orb': 6},
        'Square': {'degree': 90, 'orb': 6},
        'Sextile': {'degree': 60, 'orb': 4},
    }
    
    planet_names = list(planets.keys())
    
    # Check each pair of planets
    for i in range(len(planet_names)):
        for j in range(i + 1, len(planet_names)):
            planet1_name = planet_names[i]
            planet2_name = planet_names[j]
            planet1 = planets[planet1_name]
            planet2 = planets[planet2_name]
            
            # Calculate angular difference
            angle_diff = abs(planet1.longitude - planet2.longitude)
            
            # Handle the circular nature of degrees (0-360)
            if angle_diff > 180:
                angle_diff = 360 - angle_diff
            
            # Check if this angle matches any major aspect
            for aspect_name, aspect_info in major_aspects.items():
                target_degree = aspect_info['degree']
                orb = aspect_info['orb']
                
                # Check if the angle is within orb of the target degree
                if abs(angle_diff - target_degree) <= orb:
                    orb_value = abs(angle_diff - target_degree)
                    
                    # Determine if aspect is applying or separating based on planetary speeds
                    is_applying = _is_aspect_applying(
                        planet1_name, planet1.longitude,
                        planet2_name, planet2.longitude,
                        target_degree
                    )
                    
                    aspect = AspectData(
                        planet1=planet1_name,
                        planet2=planet2_name,
                        aspectType=aspect_name,
                        orb=orb_value,
                        isApplying=is_applying
                    )
                    aspects.append(aspect)
                    break  # Only one aspect per planet pair
    
    logger.debug(f"Calculated {len(aspects)} aspects")
    return aspects

@app.post("/api/chat")
async def chat_with_guru_streaming(chat_message: ChatMessage, user_info: dict = Depends(require_non_anonymous_user)):
    """Chat with the astrological guru using birth chart and current planetary data with streaming"""
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
        
        logger.debug("Starting streaming chat request to Claude API...")
        
        async def generate_streaming_response():
            try:
                # Start streaming the Claude response
                accumulated_text = ""
                
                # Call Claude API with streaming enabled
                with claude_client.messages.stream(
                    model="claude-3-haiku-20240307",
                    max_tokens=1000,  # Allow reasonable response length
                    temperature=0.8,
                    messages=[
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                ) as stream:
                    # Use the text_stream property for easier text handling
                    for delta_text in stream.text_stream:
                        accumulated_text += delta_text
                        
                        # Send incremental update
                        response_data = {
                            "type": "text_delta",
                            "data": {
                                "delta": delta_text,
                                "accumulated_text": accumulated_text
                            }
                        }
                        yield f"data: {json.dumps(response_data)}\n\n"
                        
                        # Add small delay to prevent overwhelming the client
                        await asyncio.sleep(0.01)
                
                # Determine if response contains meaningful astrological content
                # Only include planetary data if the response is actually giving astrological guidance
                astrological_phrases = [
                    'your aries', 'your taurus', 'your gemini', 'your cancer', 'your leo', 'your virgo',
                    'your libra', 'your scorpio', 'your sagittarius', 'your capricorn', 'your aquarius', 'your pisces',
                    'sun in', 'moon in', 'mercury in', 'venus in', 'mars in', 'jupiter in', 'saturn in',
                    'transit', 'aspect', 'retrograde', 'full moon', 'new moon', 'horoscope',
                    'astrological', 'planetary', 'birth chart', 'natal chart'
                ]
                
                # Check if response contains meaningful astrological content (not just casual mentions)
                response_lower = accumulated_text.lower()
                contains_astrology = any(phrase in response_lower for phrase in astrological_phrases)
                
                logger.debug(f"Response: '{accumulated_text}'")
                logger.debug(f"Contains astrology: {contains_astrology}")
                
                # Send completion signal with planetary data only if relevant
                completion_data = {
                    "type": "completion",
                    "data": {
                        "response": accumulated_text,
                        "currentPlanetaryData": current_planetary_data.dict() if contains_astrology else None
                    }
                }
                yield f"data: {json.dumps(completion_data)}\n\n"
                
            except anthropic.APIError as e:
                error_data = {
                    "type": "error",
                    "data": {
                        "error": f"AI chat service error: {str(e)}"
                    }
                }
                yield f"data: {json.dumps(error_data)}\n\n"
            except Exception as e:
                error_data = {
                    "type": "error", 
                    "data": {
                        "error": f"Error in chat service: {str(e)}"
                    }
                }
                yield f"data: {json.dumps(error_data)}\n\n"
        
        return StreamingResponse(
            generate_streaming_response(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream",
            }
        )
        
    except Exception as e:
        logger.error(f"Exception occurred during chat setup: {str(e)}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error setting up chat service: {str(e)}")

@app.post("/api/chat-legacy", response_model=ChatResponse)
async def chat_with_guru_legacy(chat_message: ChatMessage, user_info: dict = Depends(require_non_anonymous_user)):
    """Legacy non-streaming chat endpoint for fallback"""
    logger.debug(f"Received legacy chat message: {chat_message.message[:50]}...")
    
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
            max_tokens=50,  # Force very short text message style
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
    
    prompt = f"""You are a knowledgeable astrological friend. You have the user's birth chart and can give great astrological insights when they want them.

User's Chart: {birth_chart_context}
Current Sky: {current_planetary_context}

Recent chat: {chr(10).join(chat_history[-4:] if chat_history else [])}

User says: "{message}"

How to respond:
- Love/relationships, career, timing, life advice questions → USE their chart! Give astrological insights
- Random greetings or small talk → just be friendly, no need for astrology 
- Keep responses short like a text (1-2 sentences)
- Be warm and helpful
- IMPORTANT: Keep your response under 1000 tokens to ensure it streams completely

Reply:"""
    
    return prompt


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)