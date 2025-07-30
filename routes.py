"""API routes for the Cosmic Guru application."""

import anthropic
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import json
import asyncio
import traceback
import time

from config import get_logger, ANTHROPIC_API_KEY
from auth import verify_firebase_token, get_firestore_client
from models import (
    BirthData, AstrologicalChart, CurrentLocation, PersonalityAnalysis, AnalysisRequest,
    CurrentPlanetaryData, ChatMessage, ChatResponse, UserProfile, 
    ProfileCreationRequest, ChatRequest, PartnerData, AddPartnerRequest,
    RelationshipAnalysisRequest, RelationshipScoreResponse, HoroscopeRequest, HoroscopeResponse
)
from astrology import generate_birth_chart, current_chart
from chat_logic import (
    validate_user_profile, build_astrological_context, build_chat_context,
    convert_firebase_messages_to_chat_history, generate_semantic_kernel_streaming_response,
    create_error_response_data, save_chat_history_to_firebase, load_chat_history_from_firebase,
    create_chat_history_reducer
)
from profile_logic import (
    validate_database_availability, create_user_profile_data, save_profile_to_database,
    get_profile_from_database, validate_profile_creation_request, create_partner_data,
    add_partner_to_profile
)
from relationship_logic import (
    calculate_relationship_score, get_compatibility_level, analyze_relationship_details,
    generate_relationship_interpretation
)

logger = get_logger(__name__)

# Profile cache to avoid repeated Firebase queries
class ProfileCache:
    def __init__(self, ttl_minutes: float = 30):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.cache_times: Dict[str, float] = {}
        self.ttl_seconds = ttl_minutes * 60
    
    def get(self, user_id: str) -> Optional[Dict[str, Any]]:
        if user_id not in self.cache:
            return None
            
        # Check if cache entry has expired
        if time.time() - self.cache_times[user_id] > self.ttl_seconds:
            self.invalidate(user_id)
            return None
            
        return self.cache[user_id]
    
    def set(self, user_id: str, profile: Dict[str, Any]) -> None:
        self.cache[user_id] = profile
        self.cache_times[user_id] = time.time()
        logger.debug(f"Profile cached for user: {user_id}")
    
    def invalidate(self, user_id: str) -> None:
        self.cache.pop(user_id, None)
        self.cache_times.pop(user_id, None)
        logger.debug(f"Profile cache invalidated for user: {user_id}")
    
    def clear(self) -> None:
        self.cache.clear()
        self.cache_times.clear()
        logger.debug("Profile cache cleared")

# Initialize profile cache (30 minute TTL)
profile_cache = ProfileCache(ttl_minutes=30)

def get_user_profile_cached(user_id: str, db) -> Dict[str, Any]:
    """Get user profile with caching to avoid repeated Firebase queries."""
    # Try to get from cache first
    cached_profile = profile_cache.get(user_id)
    if cached_profile is not None:
        logger.debug(f"Profile retrieved from cache for user: {user_id}")
        return cached_profile
    
    # Cache miss - fetch from Firebase
    logger.debug(f"Profile cache miss, fetching from Firebase for user: {user_id}")
    assert db is not None, "Database client is None"
    profile_ref = db.collection('user_profiles').document(user_id)
    profile_doc = profile_ref.get()
    
    if not profile_doc.exists:
        raise HTTPException(status_code=404, detail="User profile not found")
    
    profile = profile_doc.to_dict()
    
    # Cache the profile
    profile_cache.set(user_id, profile)
    
    return profile

# Initialize Claude API client
claude_client = None
try:
    if ANTHROPIC_API_KEY:
        claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        logger.info("Claude API client initialized successfully")
    else:
        logger.warning("ANTHROPIC_API_KEY environment variable not set - personality analysis will be disabled")
except Exception as e:
    logger.error(f"Failed to initialize Claude API client: {e}")
    claude_client = None

# Create router
router = APIRouter()

@router.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Cosmic Guru API is running"}

@router.post("/api/generate-chart", response_model=AstrologicalChart)
async def generate_chart_endpoint(
    birth_data: BirthData,
    user: dict = Depends(verify_firebase_token)
):
    """Generate an astrological chart from birth data."""
    logger.debug(f"Received birth data: {birth_data}")
    try:
        # Generate the chart directly
        chart = generate_birth_chart(birth_data)
        
        # Store chart in user profile
        try:
            db = get_firestore_client()
            if db is not None:
                doc_ref = db.collection('user_profiles').document(user['uid'])
                doc_ref.update({
                    'astrological_chart': chart.model_dump(),
                    'updated_at': datetime.now()
                })
                # Invalidate profile cache
                profile_cache.invalidate(user['uid'])
                logger.debug(f"Chart stored in profile for user: {user['uid']}")
        except Exception as store_error:
            logger.warning(f"Failed to store chart in profile: {store_error}")
            # Don't fail the request if storage fails
        
        logger.debug("Chart generated successfully")
        return chart
        
    except Exception as e:
        logger.error(f"Error generating chart: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to generate chart: {str(e)}")

@router.post("/api/migrate-profile")
async def migrate_profile_data(
    request: dict,
    user: dict = Depends(verify_firebase_token)
):
    """Migrate profile data from anonymous user to authenticated user."""
    anonymous_uid = request.get('anonymous_uid')
    if not anonymous_uid:
        raise HTTPException(status_code=400, detail="anonymous_uid is required")
    
    logger.debug(f"Migrating profile data from {anonymous_uid} to {user['uid']}")
    
    try:
        # Get database connection
        db = get_firestore_client()
        validate_database_availability(db)
        
        # Get the anonymous user's profile
        assert db is not None, "Database client is None"
        anonymous_doc_ref = db.collection('user_profiles').document(anonymous_uid)
        anonymous_doc = anonymous_doc_ref.get()
        
        if not anonymous_doc.exists:
            logger.debug(f"No anonymous profile found for uid: {anonymous_uid}")
            return {"message": "No data to migrate"}
        
        anonymous_data = anonymous_doc.to_dict()
        if anonymous_data is None:
            logger.debug(f"Anonymous profile data is None for uid: {anonymous_uid}")
            return {"message": "No data to migrate"}
        
        # Get the current authenticated user's profile
        auth_doc_ref = db.collection('user_profiles').document(user['uid'])
        auth_doc = auth_doc_ref.get()
        
        if not auth_doc.exists:
            raise HTTPException(status_code=404, detail="Authenticated user profile not found")
        
        # Prepare migration data - only migrate chart and personality analysis
        migration_updates = {}
        
        if anonymous_data.get('astrological_chart'):
            migration_updates['astrological_chart'] = anonymous_data['astrological_chart']
            logger.debug(f"Migrating astrological chart from {anonymous_uid}")
        
        if anonymous_data.get('personality_analysis'):
            migration_updates['personality_analysis'] = anonymous_data['personality_analysis']
            logger.debug(f"Migrating personality analysis from {anonymous_uid}")
        
        # Update authenticated user's profile with migrated data
        if migration_updates:
            migration_updates['updated_at'] = datetime.now()
            auth_doc_ref.update(migration_updates)
            
            # Invalidate profile cache for authenticated user
            profile_cache.invalidate(user['uid'])
            
            logger.debug(f"Profile data migrated successfully from {anonymous_uid} to {user['uid']}")
        
        # Clean up anonymous user's profile (optional - you might want to keep it for a while)
        # anonymous_doc_ref.delete()
        
        return {
            "message": "Profile data migrated successfully",
            "migrated_fields": list(migration_updates.keys())
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error migrating profile data: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to migrate profile data: {str(e)}")

@router.post("/api/analyze-personality", response_model=PersonalityAnalysis)
async def analyze_personality(
    request: AnalysisRequest,
    user: dict = Depends(verify_firebase_token)
):
    """Analyze personality based on astrological chart."""
    logger.debug(f"Analyzing personality for user: {user['uid']}")
    
    if not claude_client:
        raise HTTPException(status_code=503, detail="Personality analysis service not available")
    
    try:
        # Create birth data
        birth_data = BirthData(
            birthTimestamp=request.birth_timestamp,
            latitude=request.latitude,
            longitude=request.longitude
        )
        
        # Generate chart
        chart = generate_birth_chart(birth_data)
        
        # Create chart summary data for the prompt parameters
        chart_summary = f"""
        Birth Chart Analysis

        Key Chart Signs:

        Sun: {chart.sunSign.name}
        Moon: {chart.moonSign.name}
        Ascendant: {chart.ascendant.name}

        Key Planetary Positions:"""
        
        for planet in chart.planets.values():
            chart_summary += f"\n- {planet.name}: {planet.degree:.1f}° {planet.sign} in House {planet.house}"
        
        # Note: Aspects removed from individual charts - only for synastry
        chart_summary += f"\n\nChart focuses on planetary positions and houses for personality analysis."
        
        # Create Semantic Kernel prompt template
        prompt_template = """Based on this astrological birth chart, provide a comprehensive personality analysis:

{{$chart_summary}}

Please provide:
1. A general personality overview (2-3 sentences)
2. 3-5 key strengths with descriptions and strength ratings (1-10)
3. 3-5 challenges or growth areas with descriptions and strength ratings (1-10)
4. Relationship insights (2-3 sentences)
5. Career guidance (2-3 sentences)
6. Life path insights (2-3 sentences)

Format your response as a JSON object with the following structure:
{
    "overview": "string",
    "strengths": [
        {
            "name": "string",
            "description": "string",
            "strength": number (1-10)
        }
    ],
    "challenges": [
        {
            "name": "string", 
            "description": "string",
            "strength": number (1-10)
        }
    ],
    "relationships": "string",
    "career": "string",
    "lifePath": "string"
}"""
        
        # Use Semantic Kernel prompt template approach with parameter substitution
        rendered_prompt = prompt_template.replace("{{$chart_summary}}", chart_summary)
        
        # Call Claude API with rendered prompt
        response = claude_client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=1000,
            messages=[{"role": "user", "content": rendered_prompt}]
        )
        
        # Parse response - cast to TextBlock to access text attribute
        from anthropic.types import TextBlock
        text_block = response.content[0]
        if isinstance(text_block, TextBlock):
            analysis_json = json.loads(text_block.text)
        else:
            raise ValueError(f"Expected TextBlock, got {type(text_block)}")
        
        # Create analysis object
        analysis = PersonalityAnalysis(**analysis_json)
        
        # Store analysis in user profile
        try:
            db = get_firestore_client()
            if db is not None:
                doc_ref = db.collection('user_profiles').document(user['uid'])
                doc_ref.update({
                    'personality_analysis': analysis.model_dump(),
                    'updated_at': datetime.now()
                })
                # Invalidate profile cache
                profile_cache.invalidate(user['uid'])
                logger.debug(f"Personality analysis stored in profile for user: {user['uid']}")
        except Exception as store_error:
            logger.warning(f"Failed to store personality analysis in profile: {store_error}")
            # Don't fail the request if storage fails
        
        logger.debug(f"Personality analysis completed for user: {user['uid']}")
        return analysis
        
    except Exception as e:
        logger.error(f"Error analyzing personality: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to analyze personality: {str(e)}")

@router.post("/api/chat")
async def chat_with_astrologer(
    request: ChatRequest,
    user: dict = Depends(verify_firebase_token),
):
    """Chat with AI astrologer using Semantic Kernel."""
    logger.debug(f"Chat request from user: {user['uid']}")
    
    try:
        # Get database connection
        db = get_firestore_client()
        validate_database_availability(db)
        
        # Get user profile with caching for context
        profile = get_user_profile_cached(user['uid'], db)
        
        # Validate profile completeness
        validate_user_profile(profile)
        
        # Load existing chat history from Firebase or create new one
        assert db is not None, "Database client is None"
        chat_history = await load_chat_history_from_firebase(user['uid'], db)
        
        if chat_history is None:
            # No existing chat history, create a new one
            chat_history = create_chat_history_reducer()
            logger.debug(f"Created new chat history for user: {user['uid']}")
        else:
            logger.debug(f"Loaded existing chat history for user: {user['uid']} ({len(chat_history.messages)} messages)")
        
        # Add current user message to the chat history
        from semantic_kernel.contents import ChatMessageContent, AuthorRole
        user_message = ChatMessageContent(
            role=AuthorRole.USER,
            content=request.message
        )
        chat_history.add_message(user_message)
        
        # Build astrological context from profile (uses stored chart if available, generates if not)
        current_location = CurrentLocation(
            latitude=profile['latitude'],
            longitude=profile['longitude']
        )
        
        context_data, current_chart = build_astrological_context(profile, current_location)
        system_message = build_chat_context(context_data)
        
        user_birth_data = BirthData(
            birthTimestamp=profile['birth_timestamp'],
            latitude=profile['latitude'],
            longitude=profile['longitude']
        )
        
        # Note: User message already added to chat_history above
        # We'll save the complete state after the assistant responds
        
        # Create streaming response with message storage
        assistant_response = ""
        
        async def generate_response():
            nonlocal assistant_response
            try:
                async for chunk in generate_semantic_kernel_streaming_response(
                    chat_history=chat_history,
                    system_message=system_message,
                    user_birth_data=user_birth_data,
                    current_location=current_location,
                    current_chart=current_chart
                ):
                    # Extract text from streaming chunks to build complete response
                    if '"type": "text_delta"' in chunk:
                        chunk_data = json.loads(chunk.split('data: ')[1].strip())
                        if chunk_data.get('type') == 'text_delta':
                            assistant_response += chunk_data['data']['delta']
                    
                    yield chunk
                
                # Add assistant response to chat history and save complete state
                if assistant_response:
                    assistant_message = ChatMessageContent(
                        role=AuthorRole.ASSISTANT,
                        content=assistant_response
                    )
                    chat_history.add_message(assistant_message)
                    
                    # Save the complete chat history state to Firebase
                    await save_chat_history_to_firebase(user['uid'], chat_history, db)
                
            except Exception as e:
                logger.error(f"Error in semantic kernel streaming response: {e}")
                yield create_error_response_data(str(e))
        
        return StreamingResponse(
            generate_response(), 
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control"
            }
        )
        
    except Exception as e:
        logger.error(f"Error in chat: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Chat service error: {str(e)}")

@router.post("/api/analyze-relationship", response_model=RelationshipScoreResponse)
async def analyze_relationship(
    request: RelationshipAnalysisRequest,
    user: dict = Depends(verify_firebase_token)
):
    """Analyze relationship compatibility between two people using synastry."""
    logger.debug(f"Relationship analysis request from user: {user['uid']}")
    
    if not claude_client:
        raise HTTPException(status_code=503, detail="Analysis service not available")
    
    try:
        # Calculate basic relationship score using Kerykeion
        score = calculate_relationship_score(
            request.person1_birth_data, 
            request.person2_birth_data
        )
        
        # Get compatibility level
        compatibility_level = get_compatibility_level(score)
        
        # Get detailed analysis
        details = analyze_relationship_details(
            request.person1_birth_data,
            request.person2_birth_data
        )
        
        # Generate base interpretation
        explanation, strengths, challenges, advice = generate_relationship_interpretation(
            score, compatibility_level, details
        )
        
        # Enhance interpretation with Claude AI
        enhanced_prompt = f"""As an expert astrologer, provide a detailed relationship analysis based on this synastry data:

Relationship Score: {score} points ({compatibility_level})
Person 1 - Sun: {details.get('sun_sign_person1', 'Unknown')}, Moon: {details.get('moon_sign_person1', 'Unknown')}, Ascendant: {details.get('ascendant_person1', 'Unknown')}
Person 2 - Sun: {details.get('sun_sign_person2', 'Unknown')}, Moon: {details.get('moon_sign_person2', 'Unknown')}, Ascendant: {details.get('ascendant_person2', 'Unknown')}

Base Analysis: {explanation}

Please provide an enhanced, personalized analysis that:
1. Explains the astrological dynamics between these specific sign combinations
2. Offers practical relationship advice
3. Highlights both opportunities and challenges
4. Keeps a balanced, insightful tone

Focus on the unique interplay between their Sun, Moon, and Ascendant signs."""

        # Call Claude for enhanced analysis
        response = claude_client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=800,
            messages=[{"role": "user", "content": enhanced_prompt}]
        )
        
        # Parse Claude response
        from anthropic.types import TextBlock
        text_block = response.content[0]
        if isinstance(text_block, TextBlock):
            enhanced_explanation = text_block.text
        else:
            enhanced_explanation = explanation
        
        # Create response
        analysis_response = RelationshipScoreResponse(
            total_score=score,
            compatibility_level=compatibility_level,
            explanation=enhanced_explanation,
            strengths=strengths,
            challenges=challenges,
            advice=advice
        )
        
        logger.debug(f"Relationship analysis completed for user: {user['uid']}")
        return analysis_response
        
    except Exception as e:
        logger.error(f"Error analyzing relationship: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to analyze relationship: {str(e)}")

@router.post("/api/generate-horoscope", response_model=HoroscopeResponse)
async def generate_horoscope(
    request: HoroscopeRequest,
    user: dict = Depends(verify_firebase_token)
):
    """Generate personalized horoscope based on birth data and current transits."""
    logger.debug(f"Horoscope request from user: {user['uid']}")
    
    if not claude_client:
        raise HTTPException(status_code=503, detail="Horoscope service not available")
    
    try:
        # Generate birth chart for context
        chart = generate_birth_chart(request.birth_data)
        
        # Create horoscope prompt with birth chart context
        today = datetime.now().strftime("%Y-%m-%d")
        
        horoscope_prompt = f"""As an expert astrologer, create a personalized {request.horoscope_type} horoscope for {today}.

Birth Chart Context:
- Sun Sign: {chart.sunSign.name} ({chart.sunSign.element}, {chart.sunSign.modality})
- Moon Sign: {chart.moonSign.name} ({chart.moonSign.element}, {chart.moonSign.modality})
- Ascendant: {chart.ascendant.name} ({chart.ascendant.element}, {chart.ascendant.modality})

Please provide:
1. A personalized {request.horoscope_type} horoscope (2-3 paragraphs)
2. Key astrological influences for today
3. Practical guidance and advice
4. Lucky numbers (3-5 numbers)
5. Lucky colors (2-3 colors)

Format as engaging, insightful guidance that feels personal and actionable. Consider current planetary transits affecting this person's chart."""

        # Call Claude for horoscope generation
        response = claude_client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=600,
            messages=[{"role": "user", "content": horoscope_prompt}]
        )
        
        # Parse Claude response
        from anthropic.types import TextBlock
        text_block = response.content[0]
        if isinstance(text_block, TextBlock):
            horoscope_content = text_block.text
        else:
            horoscope_content = "Unable to generate horoscope at this time."
        
        # Extract key influences, lucky numbers, and colors from the response
        # For now, we'll provide defaults and enhance parsing later
        key_influences = [
            f"Sun in {chart.sunSign.name}",
            f"Moon in {chart.moonSign.name}",
            f"{chart.ascendant.name} Rising"
        ]
        
        lucky_numbers = [7, 13, 21, 28, 35]  # Example numbers
        lucky_colors = ["Blue", "Green", "Gold"]  # Example colors
        
        horoscope_response = HoroscopeResponse(
            date=today,
            horoscope_type=request.horoscope_type,
            content=horoscope_content,
            key_influences=key_influences,
            lucky_numbers=lucky_numbers,
            lucky_colors=lucky_colors
        )
        
        logger.debug(f"Horoscope generated for user: {user['uid']}")
        return horoscope_response
        
    except Exception as e:
        logger.error(f"Error generating horoscope: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to generate horoscope: {str(e)}")

