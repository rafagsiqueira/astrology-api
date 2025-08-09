"""API routes for the Cosmic Guru application."""

import anthropic
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from kerykeion.relationship_score import RelationshipScoreFactory
from datetime import datetime
import json
import traceback
from contexts import build_birth_chart_context, build_chat_context, build_horoscope_context, build_personality_context, build_relationship_context, build_composite_context, parse_chart_response, parse_personality_response, parse_relationship_response, parse_composite_response
from profile_cache import cache, get_user_profile_cached
from analytics_service import get_analytics_service
from appstore_notifications import get_notification_handler
from astrology import create_astrological_subject

from config import get_logger, get_claude_client
from auth import verify_firebase_token, get_firestore_client, validate_database_availability
from models import (
    BirthData, AstrologicalChart, CurrentLocation, PersonalityAnalysis, AnalysisRequest, ChatRequest, RelationshipAnalysis,
    RelationshipAnalysisRequest, HoroscopeRequest, HoroscopeResponse, CompositeAnalysisRequest, CompositeAnalysis,
    DailyTransitRequest, DailyTransitResponse, DailyHoroscopeRequest, DailyHoroscopeResponse
)
from astrology import create_astrological_subject, generate_birth_chart, generate_composite_chart, generate_transits
from chat_logic import (
    validate_user_profile,
    load_chat_history_from_firebase,
    create_chat_history_reducer
)

logger = get_logger(__name__)

# Create router
router = APIRouter()

def assert_stop_reason_end_turn(response):
    """Assert that the Claude API response has stop_reason 'end_turn'.
    
    Raises:
        HTTPException: If stop_reason is not 'end_turn'
    """
    if hasattr(response, 'stop_reason') and response.stop_reason != 'end_turn':
        logger.error(f"Claude API response had unexpected stop_reason: {response.stop_reason}")
        raise HTTPException(
            status_code=502, 
            detail=f"AI response incomplete (stop_reason: {response.stop_reason}). Please try again."
        )
    elif not hasattr(response, 'stop_reason'):
        logger.warning("Claude API response missing stop_reason attribute")

def assert_end_turn(response):
    """Alias for assert_stop_reason_end_turn for backward compatibility."""
    assert_stop_reason_end_turn(response)

async def call_claude_with_analytics(claude_client, endpoint_name: str, user_id: str, **claude_kwargs):
    """Wrapper for Claude API calls that tracks 429 errors and token usage to Google Analytics.
    
    Args:
        claude_client: The Claude API client
        endpoint_name: Name of the endpoint for tracking (e.g., "generate-chart")
        user_id: User ID for analytics
        **claude_kwargs: Arguments to pass to claude_client.messages.create()
        
    Returns:
        Claude API response
        
    Raises:
        HTTPException: For various error conditions including 429
    """
    try:
        response = claude_client.messages.create(**claude_kwargs)
        
        # Track token usage on successful response
        if hasattr(response, 'usage') and response.usage:
            analytics = get_analytics_service()
            await analytics.track_claude_token_usage(
                endpoint=endpoint_name,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                user_id=user_id
            )
            logger.debug(f"Token usage tracked for {endpoint_name}: {response.usage.input_tokens} in, {response.usage.output_tokens} out")
        
        return response
    except anthropic.RateLimitError as e:
        # Track the 429 rate limit error to Google Analytics
        analytics = get_analytics_service()
        await analytics.track_claude_rate_limit(endpoint_name, user_id)
        logger.warning(f"Claude rate limit (429) tracked for endpoint {endpoint_name}, user {user_id}")
        
        # Re-raise as HTTPException
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Please try again later.")
    except anthropic.APIError as e:
        # Handle other Anthropic API errors
        logger.error(f"Claude API error on {endpoint_name}: {e}")
        raise HTTPException(status_code=503, detail="Claude API service temporarily unavailable")
    except Exception as e:
        # Handle unexpected errors
        logger.error(f"Unexpected error calling Claude API on {endpoint_name}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

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
    
    claude_client = get_claude_client()
    if not claude_client:
        raise HTTPException(status_code=503, detail="Personality analysis service not available")
    
    try:

        # Generate the chart
        chart = generate_birth_chart(birth_data)

        (system, user_message) = build_birth_chart_context(chart)

        # Call Claude API with rendered prompt and analytics tracking
        response = await call_claude_with_analytics(
            claude_client=claude_client,
            endpoint_name="generate-chart",
            user_id=user['uid'],
            model="claude-3-5-haiku-latest",
            max_tokens=2048,
            system=[
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"}
                }
            ],
            messages=[
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": "{"}
            ]
        )

        assert_end_turn(response)
        
        # Parse response - cast to TextBlock to access text attribute
        from anthropic.types import TextBlock
        text_block = response.content[0]
        if isinstance(text_block, TextBlock):
            analysis = parse_chart_response(text_block.text)
            logger.debug("Chart generation completed successfully")
            chart.analysis = analysis
            return chart
        else:
            raise ValueError(f"Expected TextBlock, got {type(text_block)}")
    except Exception as e:
        logger.error(f"Error generating chart: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to generate chart: {str(e)}")

@router.post("/api/analyze-personality", response_model=PersonalityAnalysis)
async def analyze_personality(
    request: AnalysisRequest,
    user: dict = Depends(verify_firebase_token)
):
    """Analyze personality based on astrological chart."""
    logger.debug(f"Analyzing personality for user: {user['uid']}")

    claude_client = get_claude_client()
    if not claude_client:
        raise HTTPException(status_code=503, detail="Personality analysis service not available")
    
    try:
        (system, user_message) = build_personality_context(request)
        
        # Call Claude API with rendered prompt and analytics tracking
        response = await call_claude_with_analytics(
            claude_client=claude_client,
            endpoint_name="analyze-personality",
            user_id=user['uid'],
            model="claude-3-5-haiku-latest",
            max_tokens=2048,
            system=[
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"}
                }
            ],
            messages=[
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": "{"}
            ]
        )

        assert_end_turn(response)
        
        # Parse response - cast to TextBlock to access text attribute
        from anthropic.types import TextBlock
        text_block = response.content[0]
        if isinstance(text_block, TextBlock):
            analysis = parse_personality_response(text_block.text)
            logger.debug("Personality analysis completed successfully")
            return analysis
        else:
            raise ValueError(f"Expected TextBlock, got {type(text_block)}")
        
    except Exception as e:
        logger.error(f"Error analyzing personality: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to analyze personality: {str(e)}")

@router.post("/api/analyze-relationship", response_model=RelationshipAnalysis)
async def analyze_relationship(
    request: RelationshipAnalysisRequest,
    user: dict = Depends(verify_firebase_token)
):
    """Analyze relationship compatibility between two people using synastry."""
    logger.debug(f"Relationship analysis request from user: {user['uid']}")

    claude_client = get_claude_client()
    if not claude_client:
        raise HTTPException(status_code=503, detail="Analysis service not available")
    
    try:

        person1 = create_astrological_subject(request.person1, "Person1")
        person2 = create_astrological_subject(request.person2, "Person2")
        # Use RelationshipScoreFactory for comprehensive analysis
        score_result = RelationshipScoreFactory(person1, person2).get_relationship_score()

        birth_chart_1 = generate_birth_chart(request.person1, with_svg=True)
        birth_chart_2 = generate_birth_chart(request.person2, with_svg=True)
        
        (system, user_message) = build_relationship_context(
            chart_1=birth_chart_1,
            chart_2=birth_chart_2,
            score=score_result,
            relationship_type=request.relationship_type
        )

        # Call Claude API with rendered prompt and analytics tracking
        response = await call_claude_with_analytics(
            claude_client=claude_client,
            endpoint_name="analyze-relationship", 
            user_id=user['uid'],
            model="claude-3-5-haiku-latest",
            max_tokens=2048,
            system=[
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"}
                }
            ],           
            messages=[
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": "{"}
            ]
        )

        assert_end_turn(response)

        # Parse response - cast to TextBlock to access text attribute
        from anthropic.types import TextBlock
        text_block = response.content[0]
        if isinstance(text_block, TextBlock):
            analysis = parse_relationship_response(text_block.text)
            
            # Add the chart URLs to the analysis response
            analysis.person1_chart_url = birth_chart_1.chartImageUrl
            analysis.person2_chart_url = birth_chart_2.chartImageUrl
            
            logger.debug("Relationship analysis completed successfully")
            return analysis
        else:
            raise ValueError(f"Expected TextBlock, got {type(text_block)}")
    except Exception as e:
        logger.error(f"Error analyzing relationship: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to analyze relationship: {str(e)}")

@router.post("/api/analyze-composite", response_model=CompositeAnalysis)
async def analyze_composite(
    request: CompositeAnalysisRequest,
    user: dict = Depends(verify_firebase_token)
):
    """Analyze composite chart between two people using midpoint method."""
    logger.debug(f"Composite analysis request from user: {user['uid']}")

    claude_client = get_claude_client()
    if not claude_client:
        raise HTTPException(status_code=503, detail="Analysis service not available")
    
    try:
        # Generate composite chart with SVG
        composite_chart = generate_composite_chart(request, with_svg=True)
        
        # Build context for Claude analysis
        (system, user_message) = build_composite_context(composite_chart)

        # Call Claude API with rendered prompt and analytics tracking
        response = await call_claude_with_analytics(
            claude_client=claude_client,
            endpoint_name="analyze-composite", 
            user_id=user['uid'],
            model="claude-3-5-haiku-latest",
            max_tokens=2048,
            system=[
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"}
                }
            ],           
            messages=[
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": "{"}
            ]
        )

        assert_end_turn(response)
        
        # Parse response - cast to TextBlock to access text attribute
        from anthropic.types import TextBlock
        text_block = response.content[0]
        if isinstance(text_block, TextBlock):
            analysis = parse_composite_response(text_block.text)
            
            # Add the chart SVG URL to the analysis response
            analysis.chart_svg_url = composite_chart.chartImageUrl
            
            logger.debug("Composite analysis completed successfully")
            return analysis
        else:
            raise ValueError(f"Expected TextBlock, got {type(text_block)}")
    except Exception as e:
        logger.error(f"Error analyzing composite: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to analyze composite: {str(e)}")

@router.post("/api/generate-composite-chart", response_model=AstrologicalChart)
async def generate_composite_chart_endpoint(
    request: CompositeAnalysisRequest,
    user: dict = Depends(verify_firebase_token)
):
    """Generate a composite chart from two people's birth data."""
    logger.debug(f"Composite chart generation request from user: {user['uid']}")
    
    try:
        # Generate composite chart with SVG
        composite_chart = generate_composite_chart(request, with_svg=True)
        logger.debug("Composite chart generated successfully")
        return composite_chart
        
    except Exception as e:
        logger.error(f"Error generating composite chart: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to generate composite chart: {str(e)}")

@router.post("/api/chat")
async def chat_with_astrologer(
    request: ChatRequest,
    user: dict = Depends(verify_firebase_token),
):
    """Chat with AI astrologer using Semantic Kernel."""
    logger.debug(f"Chat request from user: {user['uid']}")

    claude_client = get_claude_client()
    if not claude_client:
        raise HTTPException(status_code=503, detail="Analysis service not available")
    
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
        
        (system, user_context) = build_chat_context(profile_data=profile)

        
        async def generate_streaming_response():
            full_response = ""
            try:
                with claude_client.messages.stream(
                    max_tokens=2048,
                    system=[
                        {
                            "type": "text",
                            "text": system,
                            "cache_control": {"type": "ephemeral"}
                        }
                    ],
                    messages=[
                    {
                        "role": "user", 
                        "content": chat_history.to_prompt()
                    },
                    {
                        "role": "user",
                        "content": user_context
                    },
                    {
                        "role": "user",
                        "content": request.message
                    }
                    ],
                    model="claude-opus-4-1-20250805",
                ) as stream:
                    for text in stream.text_stream:
                        full_response += text
                        # Format as Server-Sent Events
                        yield f"data: {json.dumps({'type': 'text_delta', 'data': {'delta': text}})}\n\n"
                
                # Save the complete conversation to chat history
                if full_response:
                    from semantic_kernel.contents import ChatMessageContent, AuthorRole
                    user_message = ChatMessageContent(
                        role=AuthorRole.USER,
                        content=request.message
                    )
                    assistant_message = ChatMessageContent(
                        role=AuthorRole.ASSISTANT,
                        content=full_response
                    )
                    
                    chat_history.add_message(user_message)
                    chat_history.add_message(assistant_message)
                    
                    # Save to Firebase
                    from chat_logic import save_chat_history_to_firebase
                    await save_chat_history_to_firebase(user['uid'], chat_history, db)
                
                # Send completion signal
                yield f"data: {json.dumps({'type': 'message_stop'})}\n\n"
                
            except Exception as e:
                logger.error(f"Error in chat streaming: {e}")
                yield f"data: {json.dumps({'type': 'error', 'data': {'message': str(e)}})}\n\n"

        return StreamingResponse(
            generate_streaming_response(),
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

@router.post("/api/get-daily-transits", response_model=DailyTransitResponse)
async def get_daily_transits(
    request: DailyTransitRequest,
    user: dict = Depends(verify_firebase_token)
):
    """Get transit data for a specific date."""
    logger.debug(f"Daily transit request from user: {user['uid']} for date: {request.target_date}")
    
    try:
        
        # Parse target date
        target_date = datetime.fromisoformat(request.target_date)
        
        # Generate transits for period days starting from target date
        transits = generate_transits(
            birth_data=request.birth_data,
            current_location=request.current_location,
            start_date=target_date,
            period=request.period
        )
        
        # Return transits in the expected response format
        response = DailyTransitResponse(transits=transits)
        
        logger.debug(f"Daily transit data generated successfully: {len(transits)} transits")
        return response
        
    except Exception as e:
        logger.error(f"Error generating daily transits: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to generate daily transits: {str(e)}")

@router.post("/api/appstore-notifications")
async def handle_appstore_notifications(request: dict):
    """Handle App Store Server notifications for subscription management."""
    try:
        logger.info("Received App Store Server notification")
        
        # Extract the signed payload
        signed_payload = request.get('signedPayload')
        if not signed_payload:
            logger.error("No signedPayload found in App Store notification")
            raise HTTPException(status_code=400, detail="Invalid notification format")
        
        # Process the notification
        handler = get_notification_handler()
        success, message = await handler.process_notification(signed_payload)
        
        if success:
            logger.info(f"Successfully processed App Store notification: {message}")
            return {"status": "success", "message": message}
        else:
            logger.error(f"Failed to process App Store notification: {message}")
            raise HTTPException(status_code=500, detail=message)
            
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error handling App Store notification: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=error_msg)

