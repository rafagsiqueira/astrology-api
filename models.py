"""Pydantic models for the Cosmic Guru API."""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from datetime import datetime

class BirthData(BaseModel):
    """Birth data for astrological chart generation."""
    birthTimestamp: float
    latitude: float
    longitude: float

class CurrentLocation(BaseModel):
    """Current location of subject."""
    latitude: float
    longitude: float

class PlanetPosition(BaseModel):
    """Position of a planet in the chart."""
    name: str
    degree: float
    sign: str
    house: int
    retrograde: bool = False

class HousePosition(BaseModel):
    """Position of a house cusp."""
    house: int
    degree: float
    sign: str

class AspectData(BaseModel):
    """Aspect between two planets."""
    planet1: str
    planet2: str
    aspect_type: str
    degree: float
    orb: float

class SignData(BaseModel):
    """Zodiac sign data."""
    name: str
    element: str
    modality: str
    ruling_planet: str

class AstrologicalChart(BaseModel):
    """Complete astrological chart data."""
    planets: Dict[str, PlanetPosition]
    houses: Dict[str, HousePosition]
    sunSign: SignData
    moonSign: SignData
    ascendant: SignData
    chartSvg: str
    
    def to_string(self) -> str:
        """Convert to string representation."""
        planets_str = ", ".join([f"{name}: {planet.degree:.1f}° {planet.sign} in House {planet.house}" 
                                for name, planet in self.planets.items()])
        houses_str = ", ".join([f"House {house.house}: {house.degree:.1f}° {house.sign}" 
                               for name, house in self.houses.items()])
        
        return f"""Astrological Chart:
Sun Sign: {self.sunSign.name} ({self.sunSign.element}, {self.sunSign.modality})
Moon Sign: {self.moonSign.name} ({self.moonSign.element}, {self.moonSign.modality})
Ascendant: {self.ascendant.name} ({self.ascendant.element}, {self.ascendant.modality})

Planets: {planets_str}

Houses: {houses_str}

"""

class PersonalityTrait(BaseModel):
    """A personality trait with description and strength."""
    name: str
    description: str
    strength: int = Field(ge=1, le=10)

class PersonalityAnalysis(BaseModel):
    """Complete personality analysis based on astrological chart."""
    overview: str
    strengths: List[PersonalityTrait]
    challenges: List[PersonalityTrait]
    relationships: str
    career: str
    lifePath: str

class AnalysisRequest(BaseModel):
    """Request for personality analysis."""
    birth_timestamp: float
    latitude: float
    longitude: float

class CurrentPlanetPosition(BaseModel):
    """Current position of a planet."""
    name: str
    degree: float
    sign: str
    house: int
    retrograde: bool = False

class TransitAspect(BaseModel):
    """Transit aspect between current and natal planets."""
    transiting_planet: str
    natal_planet: str
    aspect_type: str
    degree: float
    orb: float

class CurrentPlanetaryData(BaseModel):
    """Current planetary positions and transits."""
    current_date: datetime
    planets: List[CurrentPlanetPosition]
    transits: List[TransitAspect]

class ChatMessage(BaseModel):
    """Chat message for astrological consultation."""
    role: str  # "user" or "assistant" - controlled by backend only
    content: str
    timestamp: datetime

class ChatResponse(BaseModel):
    """Response from the astrological chat API."""
    response: str
    timestamp: datetime

class UserProfile(BaseModel):
    """User profile with birth data and preferences."""
    uid: str
    email: Optional[str] = None
    birth_date: datetime
    birth_time: str
    birth_location: str
    latitude: float
    longitude: float
    timezone: str
    created_at: datetime
    updated_at: datetime
    astrological_chart: Optional[AstrologicalChart] = None
    personality_analysis: Optional[PersonalityAnalysis] = None
    partners: Optional[List["PartnerData"]] = []

class PartnerData(BaseModel):
    """Partner data stored in user profile."""
    uid: str  # Generated UUID for the partner
    name: str
    birth_date: datetime
    birth_time: str
    birth_location: str
    latitude: float
    longitude: float
    timezone: str
    created_at: datetime
    astrological_chart: Optional[AstrologicalChart] = None

class AddPartnerRequest(BaseModel):
    """Request to add a partner to user profile."""
    name: str
    birth_date: datetime
    birth_time: str
    latitude: float
    longitude: float

class ProfileCreationRequest(BaseModel):
    """Request to create a new user profile."""
    birth_date: datetime
    birth_time: str
    latitude: float
    longitude: float
    timezone: str

class ChatRequest(BaseModel):
    """Request for chat with astrologer."""
    message: str

class RelationshipAnalysisRequest(BaseModel):
    """Request for relationship analysis between two people."""
    person1_birth_data: BirthData
    person2_birth_data: BirthData

class RelationshipScoreResponse(BaseModel):
    """Relationship compatibility score response."""
    total_score: int
    compatibility_level: str  # Based on Discepolo method ranges
    explanation: str
    strengths: List[str]
    challenges: List[str]
    advice: str

class HoroscopeRequest(BaseModel):
    """Request for personalized horoscope."""
    birth_data: BirthData
    horoscope_type: str = "daily"  # "daily", "weekly", "monthly"

class HoroscopeResponse(BaseModel):
    """Personalized horoscope response."""
    date: str
    horoscope_type: str
    content: str
    key_influences: List[str]
    lucky_numbers: Optional[List[int]] = None
    lucky_colors: Optional[List[str]] = None