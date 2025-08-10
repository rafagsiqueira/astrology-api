"""Pydantic models for the Cosmic Guru API."""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum
from kerykeion.kr_types import AspectModel

class BirthData(BaseModel):
    """Simplified birth data with date, time, and coordinates."""
    birth_date: str  # YYYY-MM-DD format
    birth_time: str  # HH:MM format
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

class PlanetAnalysis(BaseModel):
    """Analysis for a single planetary position."""
    influence: str
    traits: List[str]

class ChartAnalysis(BaseModel):
    """Comprehensive chart analysis with detailed planetary interpretations."""
    sun: PlanetAnalysis
    moon: PlanetAnalysis
    ascendant: PlanetAnalysis
    mercury: PlanetAnalysis
    venus: PlanetAnalysis
    mars: PlanetAnalysis
    jupiter: PlanetAnalysis
    saturn: PlanetAnalysis
    uranus: PlanetAnalysis
    neptune: PlanetAnalysis
    pluto: PlanetAnalysis

class CosmiclogicalChart(BaseModel):
    """Complete cosmiclogical chart data."""
    planets: Dict[str, PlanetPosition]
    houses: Dict[str, HousePosition]
    sunSign: SignData
    moonSign: SignData
    ascendant: SignData
    chartSvg: str
    chartImageUrl: Optional[str] = None
    analysis: Optional[ChartAnalysis] = None
    
    def to_string(self) -> str:
        """Convert to string representation."""
        planets_str = ", ".join([f"{name}: {planet.degree:.1f}° {planet.sign} in House {planet.house}" 
                                for name, planet in self.planets.items()])
        houses_str = ", ".join([f"House {house.house}: {house.degree:.1f}° {house.sign}" 
                               for name, house in self.houses.items()])
        
        return f"""Cosmiclogical Chart:
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

class PersonalityTraitsSection(BaseModel):
    """Personality traits section with description and key traits."""
    description: str
    key_traits: List[str]

class EmotionalNatureSection(BaseModel):
    """Emotional nature section with description and characteristics."""
    description: str
    emotional_characteristics: List[str]

class CommunicationIntellectSection(BaseModel):
    """Communication and intellect section with description and strengths."""
    description: str
    communication_strengths: List[str]

class RelationshipsLoveSection(BaseModel):
    """Relationships and love section with description and dynamics."""
    description: str
    relationship_dynamics: List[str]

class CareerPurposeSection(BaseModel):
    """Career and purpose section with description and potential."""
    description: str
    career_potential: List[str]

class StrengthsChallengesSection(BaseModel):
    """Strengths and challenges section with separate lists."""
    strengths: List[str]
    challenges: List[str]

class LifePathSection(BaseModel):
    """Life path section with overview and development areas."""
    overview: str
    key_development_areas: List[str]

class PersonalityAnalysis(BaseModel):
    """Complete personality analysis based on cosmiclogical chart."""
    overview: str
    personality_traits: PersonalityTraitsSection
    emotional_nature: EmotionalNatureSection
    communication_and_intellect: CommunicationIntellectSection
    relationships_and_love: RelationshipsLoveSection
    career_and_purpose: CareerPurposeSection
    strengths_and_challenges: StrengthsChallengesSection
    life_path: LifePathSection

class AnalysisRequest(BaseModel):
    """Request for personality analysis."""
    birth_date: str  # YYYY-MM-DD format
    birth_time: str  # HH:MM format
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

class ChatRole(Enum):
    ASSISTANT = 'assistant'
    USER = 'user'
    SYSTEM = 'system'

class ChatMessage(BaseModel):
    """Chat message for cosmiclogical consultation."""
    role: ChatRole
    content: str
    timestamp: datetime

class ChatResponse(BaseModel):
    """Response from the cosmiclogical chat API."""
    response: str
    timestamp: datetime

class UserProfile(BaseModel):
    """User profile with birth data and preferences."""
    uid: str
    email: Optional[str] = None
    birth_date: datetime
    birth_time: str
    latitude: float
    longitude: float
    created_at: datetime
    updated_at: datetime
    cosmiclogical_chart: Optional[CosmiclogicalChart] = None
    personality_analysis: Optional[PersonalityAnalysis] = None
    partners: Optional[List["PartnerData"]] = []

class PartnerData(BaseModel):
    """Partner data stored in user profile."""
    uid: str  # Generated UUID for the partner
    name: str
    birth_date: datetime
    birth_time: str
    latitude: float
    longitude: float
    created_at: datetime
    cosmiclogical_chart: Optional[CosmiclogicalChart] = None

class AddPartnerRequest(BaseModel):
    """Request to add a partner to user profile."""
    name: str
    birth_date: datetime
    birth_time: str
    latitude: float
    longitude: float


class ChatRequest(BaseModel):
    """Request for chat with cosmicloger."""
    message: str

class RelationshipAnalysisRequest(BaseModel):
    """Request for relationship analysis between two people."""
    person1: BirthData
    person2: BirthData
    relationship_type: str

class RelationshipAnalysis(BaseModel):
    """Claude's structured analysis content for relationship compatibility."""
    score: int
    overview: str
    compatibility_level: str
    destiny_signs: str
    relationship_aspects: list
    strengths: list
    challenges: list
    areas_for_growth: list
    person1_chart_url: Optional[str] = None
    person2_chart_url: Optional[str] = None

class HoroscopePeriod(Enum):
    day = 'day'
    week = 'week'
    month = 'month'
    year = 'year'

class HoroscopeRequest(BaseModel):
    """Request for personalized horoscope."""
    birth_data: BirthData
    current_location: CurrentLocation
    horoscope_type: HoroscopePeriod

class HoroscopeFindings(BaseModel):
    date: str
    horoscope: str
    active_aspects: list[str]
    retrograding_planets: list[str]

class HoroscopeResponse(BaseModel):
    """Personalized horoscope response."""
    overall_summary: str
    specific_findings: list[HoroscopeFindings]
    chart_urls: list[str]

class CompositeAnalysisRequest(BaseModel):
    """Request for composite chart analysis between two people."""
    person1_birth_data: BirthData
    person2_birth_data: BirthData

class CompositeAnalysis(BaseModel):
    """Complete composite chart analysis."""
    overview: str
    relationship_identity: Dict[str, List[str]]
    emotional_dynamics: Dict[str, List[str]]
    communication_style: Dict[str, List[str]]
    love_expression: Dict[str, List[str]]
    public_image: Dict[str, List[str]]
    strengths_and_challenges: Dict[str, List[str]]
    long_term_potential: Dict[str, List[str]]
    chart_svg_url: Optional[str] = None

class DailyTransitRequest(BaseModel):
    """Request for daily transit data."""
    birth_data: BirthData
    current_location: CurrentLocation
    target_date: str
    period: HoroscopePeriod = HoroscopePeriod.day

class DailyTransit(BaseModel):
    date: datetime
    aspects: list[AspectModel]
    retrograding: list[str]

class TransitChanges(BaseModel):
    """Changes in aspects and retrogrades for a specific day."""
    began: list[AspectModel]
    ended: list[AspectModel]

class RetrogradeChanges(BaseModel):
    """Changes in retrograde planets for a specific day."""
    began: list[str]
    ended: list[str]

class DailyTransitChange(BaseModel):
    """Transit changes for a specific day."""
    date: str  # YYYY-MM-DD format
    aspects: TransitChanges
    retrogrades: RetrogradeChanges

class DailyTransitResponse(BaseModel):
    """Daily transit data response."""
    transits: list[DailyTransit]
    changes: list[DailyTransitChange]

class DailyHoroscopeRequest(BaseModel):
    """Request for daily horoscope analysis."""
    birth_data: BirthData
    transit_data: DailyTransit

class DailyHoroscopeResponse(BaseModel):
    """Daily horoscope analysis response."""
    target_date: str
    horoscope_text: str
    key_themes: List[str]
    energy_level: str  # low, moderate, high, intense
    focus_areas: List[str]

class GenerateHoroscopeRequest(BaseModel):
    """Request for generating horoscope from transit changes."""
    birth_data: BirthData
    transit_changes: DailyTransitChange

class GenerateHoroscopeResponse(BaseModel):
    """Response for generated horoscope."""
    horoscope_text: str
    target_date: str