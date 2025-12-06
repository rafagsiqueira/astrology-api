"""API routes for the Avra application."""

import asyncio
import os
import hashlib
import json
import traceback
import uuid
from datetime import datetime, timedelta
from typing import Optional, cast

import openai
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from firebase_admin import firestore as firebase_firestore
from google.cloud.firestore import FieldFilter
from kerykeion.relationship_score import RelationshipScoreFactory
from pydantic import ValidationError
from appstoreserverlibrary.models.JWSTransactionDecodedPayload import JWSTransactionDecodedPayload

from contexts import (
    build_birth_chart_context,
    build_chat_context,
    build_daily_messages_context,
    build_personality_context,
    build_relationship_context,
    build_composite_context,
    parse_chart_response,
    parse_daily_messages_response,
    parse_personality_response,
    parse_relationship_response,
    parse_composite_response,
)
from profile_cache import cache, get_user_profile_cached
from analytics_service import get_analytics_service
from appstore_notifications import get_notification_handler
from astrology import (
    create_astrological_subject,
    generate_birth_chart,
    generate_composite_chart,
    generate_transits,
    diff_transits,
)

from config import OPENAI_API_KEY, get_logger, get_openai_client
from tts_service import generate_tts_audio
from auth import get_firestore_client, validate_database_availability, verify_firebase_token
from models import (
    AnalysisRequest,
    AstrologicalChart,
    BirthData,
    CurrentLocation,
    DailyTransitRequest,
    DailyTransitResponse,
    DailyWeatherForecast,
    Horoscope,
    PersonalityAnalysis,
    ChatRequest,
    RelationshipAnalysis,
    RelationshipAnalysisRequest,
    CompositeAnalysisRequest,
    CompositeAnalysis,
    ForecastLocation,
    DailyTransit,
    DailyTransitChange,
    HoroscopePeriod,
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
from subscription_verifier import SubscriptionVerifier
from subscription_models import SubscriptionStatus
from weatherkit_service import fetch_daily_weather_forecast, WeatherKitConfigurationError

logger = get_logger(__name__)

# Create router
router = APIRouter()


def _compute_location_hash(latitude: float, longitude: float) -> str:
    """Create a short, stable hash for a latitude/longitude pair."""
    normalized = f"{round(latitude, 4)}:{round(longitude, 4)}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def _normalize_city_key(city_name: str) -> str:
    """Create a stable slug identifier for a city name."""
    slug = "".join(c.lower() if c.isalnum() else "-" for c in city_name.strip())
    slug = "-".join(filter(None, slug.split("-")))
    return slug or "unknown-city"


def _get_preferred_forecast_location(firestore_client, uid: str) -> Optional[ForecastLocation]:
    """Fetch the user's preferred forecast location from Firestore."""
    try:
        user_doc = firestore_client.collection("user_profiles").document(uid).get()
        if not user_doc.exists:
            return None
        data = user_doc.to_dict() or {}
        preference = data.get("preferred_forecast_location")
        if not isinstance(preference, dict):
            return None
        city_name = preference.get("city_name")
        if not city_name:
            return None
        latitude = preference.get("latitude")
        longitude = preference.get("longitude")
        kwargs = {
            "city_name": str(city_name),
            "region": preference.get("region"),
            "country": preference.get("country"),
        }
        if latitude is not None:
            kwargs["latitude"] = float(latitude)
        if longitude is not None:
            kwargs["longitude"] = float(longitude)
        return ForecastLocation(**kwargs)
    except Exception as firestore_error:  # pragma: no cover - best effort
        logger.error("Failed to load preferred forecast location: %s", firestore_error)
        return None


def _date_key(value: datetime) -> str:
    return value.strftime("%Y-%m-%d")
def _load_cached_transits(
    firestore_client,
    uid: str,
    date_keys: list[str],
    location_key: str,
) -> dict[str, dict]:
    """Load cached transit documents for the given user/date/location."""
    results: dict[str, dict] = {}
    collection = (
        firestore_client.collection("user_profiles")
        .document(uid)
        .collection("daily_transits")
    )

    for date_key in date_keys:
        doc_id = f"{date_key}_{location_key}"
        try:
            snapshot = collection.document(doc_id).get()
        except Exception as firestore_error:  # pragma: no cover - defensive
            logger.error("Failed to load cached transit for %s: %s", doc_id, firestore_error)
            continue

        if not snapshot.exists:
            continue

        data = snapshot.to_dict() or {}
        try:
            transit_data = data.get("transit_data")
            change_data = data.get("change_data")
            messages_data = data.get("horoscope_messages") or []
            weather_data = data.get("weather")
            forecast_loc_data = data.get("forecast_location")

            transit = DailyTransit.model_validate(transit_data) if transit_data else None
            change = (
                DailyTransitChange.model_validate(change_data)
                if change_data
                else None
            )
            messages = []
            for msg in messages_data:
                if not isinstance(msg, dict):
                    continue
                if "audio_path" not in msg and "audio_url" in msg:
                    msg = {**msg, "audio_path": msg.get("audio_url")}
                messages.append(Horoscope.model_validate(msg))
            weather = (
                DailyWeatherForecast.model_validate(weather_data)
                if weather_data
                else None
            )
            forecast_location = (
                ForecastLocation.model_validate(forecast_loc_data)
                if forecast_loc_data
                else None
            )

            if transit is None:
                continue

            results[date_key] = {
                "transit": transit,
                "change": change,
                "messages": messages,
                "weather": weather,
                "forecast_location": forecast_location,
            }
        except ValidationError as validation_error:
            logger.warning(
                "Failed to validate cached transit for %s: %s",
                doc_id,
                validation_error,
            )
        except Exception as unexpected_error:  # pragma: no cover - defensive
            logger.error(
                "Unexpected error loading cached transit for %s: %s",
                doc_id,
                unexpected_error,
            )

    return results


def _store_transit_document(
    firestore_client,
    uid: str,
    date_key: str,
    location_key: str,
    transit: DailyTransit,
    change: Optional[DailyTransitChange],
    messages: Optional[list[Horoscope]],
    weather: Optional[DailyWeatherForecast],
    forecast_location: Optional[ForecastLocation],
) -> None:
    """Persist a transit document to Firestore."""
    collection = (
        firestore_client.collection("user_profiles")
        .document(uid)
        .collection("daily_transits")
    )
    doc_id = f"{date_key}_{location_key}"
    doc_ref = collection.document(doc_id)

    try:
        payload = {
            "date": date_key,
            "location_key": location_key,
            "transit_data": transit.model_dump(mode="json"),
            "cached_at": firebase_firestore.SERVER_TIMESTAMP,
        }
        if change is not None:
            payload["change_data"] = change.model_dump(mode="json")
        if messages:
            payload["horoscope_messages"] = [
                msg.model_dump(mode="json", exclude_none=True) for msg in messages
            ]
        if weather is not None:
            payload["weather"] = weather.model_dump(mode="json")
        if forecast_location is not None:
            payload["forecast_location"] = forecast_location.model_dump(
                mode="json", exclude_none=True
            )

        doc_ref.set(payload)
    except Exception as firestore_error:  # pragma: no cover - defensive
        logger.error(
            "Failed to store transit document %s: %s", doc_id, firestore_error
        )


async def _fetch_weather_range(
    latitude: float,
    longitude: float,
    start_date: datetime,
    days: int,
) -> dict[str, DailyWeatherForecast]:
    """Fetch weather forecasts for a latitude/longitude without caching."""
    if days <= 0:
        return {}

    forecast_start = start_date
    forecast_end = start_date + timedelta(days=max(days - 1, 0))
    results: dict[str, DailyWeatherForecast] = {}

    try:
        raw_forecasts = await fetch_daily_weather_forecast(
            latitude=latitude,
            longitude=longitude,
            start_date=forecast_start,
            end_date=forecast_end,
        )
        for entry in raw_forecasts:
            try:
                forecast = DailyWeatherForecast(**entry)
            except Exception as validation_error:
                logger.warning("Skipping malformed WeatherKit entry: %s", validation_error)
                continue
            if forecast.date:
                results[forecast.date] = forecast
    except WeatherKitConfigurationError as config_error:
        logger.warning("WeatherKit configuration missing: %s", config_error)
    except Exception as weather_error:
        logger.error("Failed to fetch WeatherKit forecast: %s", weather_error)

    return results


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
            relationships_list = []
            
            # Check where user is partner_1
            relationships_ref = db.collection('relationships').where(filter=FieldFilter('partner_1_uid', '==', user_id))
            relationships_docs = relationships_ref.get()
            for doc in relationships_docs:
                if doc.exists:
                    relationships_list.append(doc.to_dict())
            
            # Also check where user is partner_2
            relationships_ref_2 = db.collection('relationships').where(filter=FieldFilter('partner_2_uid', '==', user_id))
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

@router.post("/api/transactions")
async def verify_subscription(
    request: dict,
    user: dict = Depends(verify_firebase_token)
):
    """Verify a subscription purchase with Apple."""
    transaction_id = request.get("transactionId")
    if not transaction_id:
        raise HTTPException(status_code=400, detail="Transaction ID required")

    verifier = SubscriptionVerifier()
    verified_transaction: JWSTransactionDecodedPayload = await verifier.verify_transaction(request)
    
    if not verified_transaction:
        logger.warning(f"Transaction verification failed for {transaction_id}, but allowing purchase flow to continue (frontend handles this).")
        return {"status": "verification_failed", "transaction": None}
        
    try:
        subscription_service = get_subscription_service()
        
        # Update subscription in Firestore
        await subscription_service.update_subscription_from_transaction(verified_transaction)
        
        return {"status": "verified", "transaction": verified_transaction}
        
    except Exception as e:
        logger.error(f"Error updating subscription: {e}")
        raise HTTPException(status_code=500, detail="Failed to update subscription")

@router.get("/api/subscription")
async def get_subscription_status_endpoint(
    user: dict = Depends(verify_firebase_token)
):
    """Get current subscription status and quota usage."""
    subscription_service = get_subscription_service()
    has_premium = await subscription_service.has_premium_access(user['uid'])
    
    # Get free quota usage for horoscopes
    db = get_firestore_client()
    transits_ref = db.collection("user_profiles").document(user['uid']).collection("daily_transits")
    # Count documents (this might be expensive if many, but for free users it should be small)
    # Actually, we only care if it's >= 3.
    docs = transits_ref.limit(4).get() # Get up to 4 to see if >= 3
    horoscope_count = len(docs)
    
    return {
        "isPremium": has_premium,
        "freeHoroscopesUsed": horoscope_count,
        "freeHoroscopeLimit": 3
    }

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
    
    # Check premium access
    subscription_service = get_subscription_service()
    has_premium = await subscription_service.has_premium_access(user['uid'])
    if not has_premium:
        raise HTTPException(status_code=403, detail="Composite analysis is a premium feature.")
    
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
    logger.debug(
        "Daily transit request from user: %s for date: %s",
        user["uid"],
        request.target_date,
    )

    try:
        validate_database_availability()
        firestore_client = get_firestore_client()
        if firestore_client is None:
            raise HTTPException(
                status_code=503,
                detail="Firestore service unavailable",
            )

        # Resolve effective location from user preference or request payload.
        preferred_location = _get_preferred_forecast_location(
            firestore_client, user["uid"]
        )
        effective_latitude = preferred_location.latitude if preferred_location and preferred_location.latitude is not None else request.current_location.latitude
        effective_longitude = preferred_location.longitude if preferred_location and preferred_location.longitude is not None else request.current_location.longitude
        effective_city = preferred_location.city_name if preferred_location else None

        location_key = (
            _normalize_city_key(effective_city)
            if effective_city
            else _compute_location_hash(effective_latitude, effective_longitude)
        )

        # Determine requested period length.
        try:
            target_date = datetime.fromisoformat(request.target_date)
        except ValueError as parse_error:
            raise HTTPException(status_code=400, detail="Invalid target date") from parse_error

        # Global Restriction: Only Daily Horoscopes allowed
        if request.period != HoroscopePeriod.day:
             raise HTTPException(status_code=400, detail="Only daily horoscopes are available.")

        # Global Restriction: Validate Target Date (Today or Tomorrow > 8PM)
        # We use server time for consistency
        now = datetime.now() # Server local time (assuming server is configured correctly or we use UTC)
        # Ideally we should handle timezones properly. For now, using server local time.
        today = now.date()
        
        # Parse target_date
        # target_date is already a datetime object from line 1022
        target_date_obj = target_date.date()

        allowed_dates = [today]
        
        # 8 PM Rule: Allow tomorrow if it's after 8 PM (20:00)
        if now.hour >= 20:
            allowed_dates.append(today + timedelta(days=1))
            
        if target_date_obj not in allowed_dates:
             # We might want to allow PAST dates if they are already cached/unlocked?
             # The requirement says "can only request today's horoscope".
             # Usually users want to see "Today".
             # If they try to request a future date not allowed, block.
             # If they try to request a past date... strictly speaking, "only request today's".
             # Let's be strict.
             raise HTTPException(status_code=403, detail="You can only view today's horoscope.")

        period_days = 1
        date_keys = [_date_key(target_date + timedelta(days=i)) for i in range(period_days)]

        # Enforce limits for non-premium users
        subscription_service = get_subscription_service()
        has_premium = await subscription_service.has_premium_access(user['uid'])
        
        if not has_premium:
            # Check quota (3 unique horoscopes)
            # We check if the requested date/location ALREADY exists in Firestore.
            # If it exists, we allow it (re-read).
            # If it doesn't exist, we check if they have room in their quota.
            
            # Note: _load_cached_transits returns what exists.
            # But we haven't called it yet with the specific logic for quota.
            
            # Let's check if it exists first.
            # We need to know if we are going to generate new content.
            
            # Re-using the logic below: _load_cached_transits checks for existence.
            # But we need to do this check BEFORE we decide to generate.
            
            # Let's peek at the cache for the requested date/location
            doc_id = f"{date_keys[0]}_{location_key}" # We know it's 1 day
            doc_ref = firestore_client.collection("user_profiles").document(user['uid']).collection("daily_transits").document(doc_id)
            doc_snap = doc_ref.get()
            
            if not doc_snap.exists:
                # It's a new request. Check quota.
                transits_ref = firestore_client.collection("user_profiles").document(user['uid']).collection("daily_transits")
                # We count how many they have.
                # Optimization: We can store the count in the user profile or just count here.
                # Since limit is small (3), counting is fine.
                existing_docs = transits_ref.limit(3).get()
                if len(existing_docs) >= 3:
                     raise HTTPException(status_code=403, detail="Free horoscope quota exceeded (3/3). Upgrade to Premium for unlimited access.")

        cached_transits = _load_cached_transits(
            firestore_client,
            user["uid"],
            date_keys,
            location_key,
        )

        # Fetch weather forecasts for the requested range.
        weather_forecasts_raw = await _fetch_weather_range(
            effective_latitude,
            effective_longitude,
            target_date,
            period_days,
        )

        weather_forecasts_map: dict[str, DailyWeatherForecast] = {}
        for key, value in weather_forecasts_raw.items():
            if isinstance(value, DailyWeatherForecast):
                weather_forecasts_map[key] = value
            elif isinstance(value, dict):
                try:
                    weather_forecasts_map[key] = DailyWeatherForecast.model_validate(value)
                except ValidationError:
                    continue
            else:
                continue

        missing_dates = [date_key for date_key in date_keys if date_key not in cached_transits]
        generated_transits: dict[str, dict] = {}

        if missing_dates:
            openai_client = get_openai_client()
            if not openai_client:
                raise HTTPException(
                    status_code=503,
                    detail="Horoscope generation service not available",
                )

            if (
                preferred_location
                and preferred_location.latitude is not None
                and preferred_location.longitude is not None
            ):
                effective_location = CurrentLocation(
                    latitude=effective_latitude,
                    longitude=effective_longitude,
                )
            else:
                effective_location = request.current_location

            transits = generate_transits(
                birth_data=request.birth_data,
                current_location=effective_location,
                start_date=target_date,
                period=request.period,
            )

            changes = diff_transits(transits)

            weather_context = [
                weather_forecasts_map[date_key]
                for date_key in date_keys
                if date_key in weather_forecasts_map
            ]

            system_prompt, user_prompt = build_daily_messages_context(
                request.birth_data,
                changes,
                weather_context,
            )

            response = await call_openai_with_analytics(
                openai_client=openai_client,
                endpoint_name="generate-horoscope",
                user_id=user["uid"],
                model="gpt-4o-mini",
                max_output_tokens=1000,
                temperature=0.7,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                    {"role": "assistant", "content": "{"},
                ],
            )

            messages_text = extract_response_text(response)
            generated_messages: list[Horoscope] = parse_daily_messages_response(messages_text)

            user_id_for_audio = user["uid"]

            async def synthesise_audio(message: Horoscope) -> Optional[tuple[str, str, str]]:
                script = message.audioscript or message.message
                if not script:
                    return None
                message_id = message.message_id or str(uuid.uuid4())

                def _call_tts():
                    try:
                        path, audio_format = generate_tts_audio(
                            script=script,
                            user_id=user_id_for_audio,
                            date_key=message.date,
                            message_id=message_id,
                            openai_client=openai_client,
                        )
                        return path, audio_format, message_id
                    except Exception as tts_error:
                        logger.error("TTS synthesis failed: %s", tts_error)
                        return None

                return await asyncio.to_thread(_call_tts)

            audio_tasks = [
                synthesise_audio(message)
                for message in generated_messages
            ]
            audio_results = await asyncio.gather(*audio_tasks, return_exceptions=True)

            for message, audio_payload in zip(generated_messages, audio_results):
                if isinstance(audio_payload, Exception):
                    logger.error("Audio synthesis errored for message %s: %s", message.message_id, audio_payload)
                    continue
                if not audio_payload:
                    continue
                audio_path, audio_format, resolved_message_id = audio_payload
                message.audio_path = cast(str, audio_path)
                message.audio_format = audio_format
                if not message.message_id:
                    message.message_id = resolved_message_id
                message.voice = "alloy"

            transits_by_date = {
                _date_key(transit.date): transit for transit in transits
            }
            changes_by_date = {change.date: change for change in changes}

            messages_by_date: dict[str, list[Horoscope]] = {}
            for message in generated_messages:
                if not message.date:
                    continue
                messages_by_date.setdefault(message.date, []).append(message)

            response_forecast_location = preferred_location

            for date_key in missing_dates:
                transit = transits_by_date.get(date_key)
                if transit is None:
                    continue
                change = changes_by_date.get(date_key)
                day_messages = messages_by_date.get(date_key, [])
                weather = weather_forecasts_map.get(date_key)

                generated_transits[date_key] = {
                    "transit": transit,
                    "change": change,
                    "messages": day_messages,
                    "weather": weather,
                    "forecast_location": response_forecast_location,
                }

                _store_transit_document(
                    firestore_client=firestore_client,
                    uid=user["uid"],
                    date_key=date_key,
                    location_key=location_key,
                    transit=transit,
                    change=change,
                    messages=day_messages,
                    weather=weather,
                    forecast_location=response_forecast_location,
                )

        combined = {**cached_transits, **generated_transits}

        ordered_transits: list[DailyTransit] = []
        ordered_changes: list[DailyTransitChange] = []
        ordered_messages: list[Horoscope] = []
        ordered_weather: list[DailyWeatherForecast] = []

        for date_key in date_keys:
            entry = combined.get(date_key)
            if not entry:
                continue
            transit = entry.get("transit")
            change = entry.get("change")
            messages = entry.get("messages") or []
            weather = entry.get("weather")

            if transit:
                ordered_transits.append(transit)
            if change:
                ordered_changes.append(change)
            if messages:
                ordered_messages.extend(messages)
            if weather and all(existing.date != weather.date for existing in ordered_weather):
                ordered_weather.append(weather)

        forecast_location_response = preferred_location
        if forecast_location_response is None and effective_city:
            forecast_location_response = ForecastLocation(
                city_name=effective_city,
                latitude=effective_latitude,
                longitude=effective_longitude,
            )

        return DailyTransitResponse(
            transits=ordered_transits,
            changes=ordered_changes,
            messages=ordered_messages or None,
            weather=ordered_weather or None,
            forecast_location=forecast_location_response,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error generating daily transits: %s", exc)
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate daily transits: {exc}",
        ) from exc

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
