"""API routes for the Avra application."""

import openai
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from kerykeion.relationship_score import RelationshipScoreFactory
from datetime import datetime
import json
import traceback
from contexts import build_birth_chart_context, build_chat_context, build_daily_messages_context, build_personality_context, build_relationship_context, build_composite_context, parse_chart_response, parse_daily_messages_response, parse_personality_response, parse_relationship_response, parse_composite_response
from profile_cache import cache, get_user_profile_cached
from analytics_service import get_analytics_service
from appstore_notifications import get_notification_handler
from astrology import create_astrological_subject, create_astrological_subject, generate_birth_chart, generate_composite_chart, generate_transits, diff_transits

from config import get_logger, get_openai_client, OPENAI_API_KEY
from auth import verify_firebase_token, get_firestore_client, validate_database_availability
from models import (
    BirthData, AstrologicalChart, Horoscope, PersonalityAnalysis, AnalysisRequest, ChatRequest, RelationshipAnalysis,
    RelationshipAnalysisRequest, CompositeAnalysisRequest, CompositeAnalysis,
    DailyTransitRequest, DailyTransitResponse
)
from chat_logic import (
    validate_user_profile,
    load_chat_history_from_firebase,
    create_chat_history_reducer,
    create_streaming_response_data,
    create_error_response_data,
    count_sentences,
    get_user_token_usage,
    update_user_token_usage
)
from subscription_service import get_subscription_service

logger = get_logger(__name__)

# Create router
router = APIRouter()

# Health check endpoint
@router.get("/health")
async def health_check():
    """Comprehensive health check endpoint that verifies all critical services."""
    from auth import get_firebase_app, get_firestore_client
    from config import get_openai_client, APP_VERSION, OPENAI_API_KEY
    
    health_status = {
        "status": "healthy",
        "service": "avra-backend",
        "version": APP_VERSION,
        "services": {
            "firebase_admin": {"status": "unknown"},
            "firestore": {"status": "unknown"},
            "openai_api": {"status": "unknown"}
        }
    }
    
    overall_healthy = True
    
    # Check Firebase Admin SDK
    try:
        import os
        firebase_app = get_firebase_app()
        if firebase_app:
            # Check if proper credentials are configured
            google_creds = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
            if not google_creds:
                # Might be using Application Default Credentials, check if they work
                from firebase_admin import auth
                try:                    
                    # This will fail if credentials are not properly set up
                    auth.get_user_by_email("test@nonexistent.com")
                except auth.UserNotFoundError:
                    # This is expected - user doesn't exist, but auth is working
                    pass
                except Exception as cred_error:
                    if "credential" in str(cred_error).lower() or "unauthorized" in str(cred_error).lower():
                        health_status["services"]["firebase_admin"]["status"] = "error"
                        health_status["services"]["firebase_admin"]["error"] = "Firebase credentials not properly configured"
                        overall_healthy = False
                        raise Exception("Firebase credentials not properly configured")
            
            health_status["services"]["firebase_admin"]["status"] = "healthy"
        else:
            health_status["services"]["firebase_admin"]["status"] = "unavailable"
            health_status["services"]["firebase_admin"]["error"] = "Firebase Admin SDK not initialized"
            overall_healthy = False
    except Exception as e:
        health_status["services"]["firebase_admin"]["status"] = "error"
        health_status["services"]["firebase_admin"]["error"] = str(e)
        overall_healthy = False
    
    # Check Firestore connectivity
    try:
        db = get_firestore_client()
        if db:
            # Test actual Firestore connectivity with a simple operation
            test_collection = db.collection('health_check')
            # This will fail if Firestore is not accessible
            list(test_collection.limit(1).stream())
            health_status["services"]["firestore"]["status"] = "healthy"
        else:
            health_status["services"]["firestore"]["status"] = "unavailable"
            health_status["services"]["firestore"]["error"] = "Firestore client not initialized"
            overall_healthy = False
    except Exception as e:
        health_status["services"]["firestore"]["status"] = "error"
        health_status["services"]["firestore"]["error"] = str(e)
        overall_healthy = False
    
    # Check OpenAI API client
    try:
        openai_client = get_openai_client()
        if openai_client and OPENAI_API_KEY:
            # Test actual API connectivity with a minimal request
            # We don't make an actual API call here to avoid costs, but verify client setup
            health_status["services"]["openai_api"]["status"] = "healthy"
        else:
            health_status["services"]["openai_api"]["status"] = "unavailable"
            health_status["services"]["openai_api"]["error"] = "OpenAI API key not configured"
            overall_healthy = False
    except Exception as e:
        health_status["services"]["openai_api"]["status"] = "error"
        health_status["services"]["openai_api"]["error"] = str(e)
        overall_healthy = False
    
    # Set overall status
    if not overall_healthy:
        health_status["status"] = "unhealthy"
        # Return 503 Service Unavailable if any critical service is down
        raise HTTPException(status_code=503, detail=health_status)
    
    return health_status


async def enhance_profile_with_chat_context(user_id: str, profile: dict, db) -> dict:
    """Enhance user profile with additional context data for chat.
    
    Args:
        user_id: Firebase user ID
        profile: Base user profile dictionary
        db: Firestore database client
        
    Returns:
        Enhanced profile dictionary with horoscopes, personality_analysis, and relationships
    """
    if not profile:
        profile = {}
    
    try:
        # Get user document reference
        user_doc_ref = db.collection('user_profiles').document(user_id)
        
        # Retrieve horoscopes subcollection
        horoscopes_data = None
        try:
            horoscopes_ref = user_doc_ref.collection('horoscopes')
            horoscopes_docs = horoscopes_ref.get()
            if horoscopes_docs:
                horoscopes_data = {}
                for doc in horoscopes_docs:
                    if doc.exists:
                        horoscopes_data[doc.id] = doc.to_dict()
        except Exception as e:
            logger.debug(f"No horoscopes found for user {user_id}: {e}")
        
        # Retrieve relationships subcollection
        relationships_data = None
        try:
            relationships_ref = db.collection('relationships').where('partner_1_uid', '==', user_id)
            relationships_docs = relationships_ref.get()
            relationships_list = []
            for doc in relationships_docs:
                if doc.exists:
                    relationships_list.append(doc.to_dict())
            
            # Also check where user is partner_2
            relationships_ref_2 = db.collection('relationships').where('partner_2_uid', '==', user_id)
            relationships_docs_2 = relationships_ref_2.get()
            for doc in relationships_docs_2:
                if doc.exists:
                    relationships_list.append(doc.to_dict())
            
            if relationships_list:
                relationships_data = relationships_list
        except Exception as e:
            logger.debug(f"No relationships found for user {user_id}: {e}")
        
        # Add the retrieved data to profile
        if horoscopes_data:
            profile['horoscopes'] = horoscopes_data
        if relationships_data:
            profile['relationships'] = relationships_data
        
        # personality_analysis should already be in the profile from the base query
        # but let's ensure it's properly handled if missing
        if 'personality_analysis' not in profile or not profile['personality_analysis']:
            try:
                # Try to get it from the main user document if not already there
                user_doc = user_doc_ref.get()
                if user_doc.exists:
                    user_data = user_doc.to_dict()
                    if user_data and 'personality_analysis' in user_data:
                        profile['personality_analysis'] = user_data['personality_analysis']
            except Exception as e:
                logger.debug(f"Could not retrieve personality analysis for user {user_id}: {e}")
        
        logger.debug(f"Enhanced profile for user {user_id} with additional context data")
        
    except Exception as e:
        logger.error(f"Error enhancing profile with chat context for user {user_id}: {e}")
        # Continue with original profile if enhancement fails
    
    return profile


def _get_usage_value(usage, attribute: str) -> int:
    """Safely extract usage values from OpenAI response objects."""

    if usage is None:
        return 0

    if hasattr(usage, attribute):
        return getattr(usage, attribute) or 0

    if isinstance(usage, dict):
        return usage.get(attribute, 0) or 0

    return 0


def extract_response_text(response) -> str:
    """Extract plain text content from an OpenAI Responses API response."""

    if hasattr(response, "output_text") and response.output_text:
        return response.output_text

    if hasattr(response, "output"):
        texts = []
        for item in getattr(response, "output", []):
            for content in getattr(item, "content", []):
                text = getattr(content, "text", None)
                if text:
                    texts.append(text)
        if texts:
            return "".join(texts)

    raise ValueError("No text content found in OpenAI response")


async def call_openai_with_analytics(openai_client, endpoint_name: str, user_id: str, **openai_kwargs):
    """Wrapper for OpenAI Responses API calls that tracks rate limits and token usage."""

    try:
        response = openai_client.responses.create(**openai_kwargs)

        usage = getattr(response, "usage", None)
        if usage:
            analytics = get_analytics_service()
            await analytics.track_model_token_usage(
                endpoint=endpoint_name,
                input_tokens=_get_usage_value(usage, "input_tokens"),
                output_tokens=_get_usage_value(usage, "output_tokens"),
                user_id=user_id
            )
            logger.debug(
                "Token usage tracked for %s: %s in, %s out",
                endpoint_name,
                _get_usage_value(usage, "input_tokens"),
                _get_usage_value(usage, "output_tokens")
            )

        return response
    except openai.RateLimitError as exc:
        analytics = get_analytics_service()
        await analytics.track_model_rate_limit(endpoint_name, user_id)
        logger.warning(
            "OpenAI rate limit (429) tracked for endpoint %s, user %s: %s",
            endpoint_name,
            user_id,
            exc
        )
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Please try again later.") from exc
    except openai.APIError as exc:
        logger.error(f"OpenAI API error on {endpoint_name}: {exc}")
        raise HTTPException(status_code=503, detail="OpenAI API service temporarily unavailable") from exc
    except Exception as exc:
        logger.error(f"Unexpected error calling OpenAI on {endpoint_name}: {exc}")
        raise HTTPException(status_code=500, detail="Internal server error") from exc

@router.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Avra API is running"}

@router.post("/api/generate-chart", response_model=AstrologicalChart)
async def generate_chart_endpoint(
    birth_data: BirthData,
    user: dict = Depends(verify_firebase_token)
):
    """Generate an astrological chart from birth data."""
    logger.debug(f"Received birth data: {birth_data}")
    
    openai_client = get_openai_client()
    if not openai_client:
        raise HTTPException(status_code=503, detail="Personality analysis service not available")
    
    try:

        # Generate the chart
        chart = generate_birth_chart(birth_data)

        (system, user_message) = build_birth_chart_context(chart)

        # Call OpenAI API with rendered prompt and analytics tracking
        response = await call_openai_with_analytics(
            openai_client=openai_client,
            endpoint_name="generate-chart",
            user_id=user['uid'],
            model="gpt-4o-mini",
            max_output_tokens=2048,
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": "{"}
            ]
        )

        analysis_text = extract_response_text(response)
        analysis = parse_chart_response(analysis_text)
        logger.debug("Chart generation completed successfully")
        chart.analysis = analysis
        return chart
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

    openai_client = get_openai_client()
    if not openai_client:
        raise HTTPException(status_code=503, detail="Personality analysis service not available")
    
    try:
        (system, user_message) = build_personality_context(request)
        
        # Call OpenAI API with rendered prompt and analytics tracking
        response = await call_openai_with_analytics(
            openai_client=openai_client,
            endpoint_name="analyze-personality",
            user_id=user['uid'],
            model="gpt-4o-mini",
            max_output_tokens=2048,
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": "{"}
            ]
        )

        analysis_text = extract_response_text(response)
        analysis = parse_personality_response(analysis_text)
        logger.debug("Personality analysis completed successfully")
        return analysis
        
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

    openai_client = get_openai_client()
    if not openai_client:
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

        # Call OpenAI API with rendered prompt and analytics tracking
        response = await call_openai_with_analytics(
            openai_client=openai_client,
            endpoint_name="analyze-relationship",
            user_id=user['uid'],
            model="gpt-4o-mini",
            max_output_tokens=2048,
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": "{"}
            ]
        )

        analysis_text = extract_response_text(response)
        analysis = parse_relationship_response(analysis_text)

        # Add the chart URLs to the analysis response
        analysis.person1_light = birth_chart_1.light_svg
        analysis.person1_dark = birth_chart_1.dark_svg
        analysis.person2_light = birth_chart_2.light_svg
        analysis.person2_dark = birth_chart_2.dark_svg

        logger.debug("Relationship analysis completed successfully")
        return analysis
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

    openai_client = get_openai_client()
    if not openai_client:
        raise HTTPException(status_code=503, detail="Analysis service not available")
    
    try:
        # Generate composite chart with SVG
        composite_chart = generate_composite_chart(request, with_svg=True)
        
        # Build context for OpenAI analysis
        (system, user_message) = build_composite_context(composite_chart)

        # Call OpenAI API with rendered prompt and analytics tracking
        response = await call_openai_with_analytics(
            openai_client=openai_client,
            endpoint_name="analyze-composite",
            user_id=user['uid'],
            model="gpt-4o-mini",
            max_output_tokens=2048,
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": "{"}
            ]
        )

        analysis_text = extract_response_text(response)
        analysis = parse_composite_response(analysis_text)

        logger.debug("Composite analysis completed successfully")
        return analysis
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
async def chat_with_guru(
    request: ChatRequest,
    user: dict = Depends(verify_firebase_token),
):
    """Chat with Avra."""
    logger.debug(f"Chat request from user: {user['uid']}")

    openai_client = get_openai_client()
    if not openai_client:
        raise HTTPException(status_code=503, detail="Analysis service not available")
    
    # Get database connection
    db = get_firestore_client()
    validate_database_availability()

    # Token limiting for non-subscribed users
    subscription_service = get_subscription_service()
    has_premium = await subscription_service.has_premium_access(user['uid'])

    if not has_premium:
        TOKEN_LIMIT = 7  # 5-7 sentences
        usage = await get_user_token_usage(user['uid'], db)
        sentences = count_sentences(request.message)
        
        if usage + sentences > TOKEN_LIMIT:
            raise HTTPException(status_code=529, detail="You have exceeded your free message limit.")
            return

        await update_user_token_usage(user['uid'], usage + sentences, db)

    try:
        # Get user profile with caching for context
        profile = get_user_profile_cached(user['uid'], db)
        
        # Validate profile completeness
        validate_user_profile(profile)
        
        # Enhance profile with additional context data for chat
        profile = await enhance_profile_with_chat_context(user['uid'], profile, db)
        
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
            final_usage = None
            try:
                with openai_client.responses.stream(
                    model="gpt-4o-mini",
                    max_output_tokens=2048,
                    input=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": chat_history.to_prompt()},
                        {"role": "user", "content": user_context},
                        {"role": "user", "content": request.message}
                    ]
                ) as stream:
                    for event in stream:
                        if event.type == "response.output_text.delta":
                            text = getattr(event, "delta", "")
                            if text:
                                full_response += text
                                yield create_streaming_response_data(text)
                        elif event.type == "response.error":
                            error_message = getattr(event, "message", "OpenAI streaming error")
                            logger.error(f"OpenAI streaming error: {error_message}")
                            yield create_error_response_data(error_message)
                    final_response = stream.get_final_response()
                    final_usage = getattr(final_response, "usage", None)

                if final_usage:
                    analytics = get_analytics_service()
                    await analytics.track_model_token_usage(
                        endpoint="chat",
                        input_tokens=_get_usage_value(final_usage, "input_tokens"),
                        output_tokens=_get_usage_value(final_usage, "output_tokens"),
                        user_id=user['uid']
                    )

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

            except openai.RateLimitError as exc:
                analytics = get_analytics_service()
                await analytics.track_model_rate_limit("chat", user['uid'])
                error_message = "Rate limit exceeded. Please try again later."
                logger.error(f"OpenAI rate limit during streaming: {exc}")
                yield create_error_response_data(error_message)
            except Exception as e:
                logger.error(f"Error in chat streaming: {e}")
                yield create_error_response_data(str(e))

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

        # Validate OpenAI client
        openai_client = get_openai_client()
        if not openai_client:
            raise HTTPException(status_code=503, detail="Horoscope generation service not available")
        
        # Parse target date
        target_date = datetime.fromisoformat(request.target_date)
        
        # Generate transits for period days starting from target date
        transits = generate_transits(
            birth_data=request.birth_data,
            current_location=request.current_location,
            start_date=target_date,
            period=request.period
        )
        
        # Generate transit changes (diff)
        changes = diff_transits(transits)

        (system_prompt, user_prompt) = build_daily_messages_context(request.birth_data, changes)

        logger.debug("Calling OpenAI API for horoscope generation")

        # Call OpenAI API with analytics tracking
        response = await call_openai_with_analytics(
            openai_client=openai_client,
            endpoint_name="generate-horoscope",
            user_id=user['uid'],
            model="gpt-4o-mini",
            max_output_tokens=1000,
            temperature=0.7,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
                {"role": "assistant", "content": "{"}
            ]
        )

        daily_transit_response = DailyTransitResponse(transits=transits, changes=changes, messages=None)
        
        messages_text = extract_response_text(response)
        messages: list[Horoscope] = parse_daily_messages_response(messages_text)
        daily_transit_response.messages = messages
        
        logger.debug(f"Daily transit data generated successfully: {len(transits)} transits")
        return daily_transit_response
        
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
