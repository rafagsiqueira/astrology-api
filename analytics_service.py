"""Google Analytics service for tracking API events."""

import asyncio
import os
from typing import Optional, Dict, Any
import httpx
from config import get_logger

logger = get_logger(__name__)

class GoogleAnalyticsService:
    """Service for tracking events to Google Analytics using Measurement Protocol."""
    
    def __init__(self):
        # Get configuration from environment variables
        self.measurement_id = os.getenv('GA_MEASUREMENT_ID')  # Format: G-XXXXXXXXXX
        self.api_secret = os.getenv('GA_API_SECRET')
        self.base_url = "https://www.google-analytics.com/mp/collect"
        
        if not self.measurement_id or not self.api_secret:
            logger.warning("Google Analytics not configured - missing GA_MEASUREMENT_ID or GA_API_SECRET")
    
    async def track_event(self, 
                         event_name: str, 
                         client_id: str = "backend-server", 
                         parameters: Optional[Dict[str, Any]] = None) -> bool:
        """Track an event to Google Analytics.
        
        Args:
            event_name: Name of the event to track
            client_id: Client identifier (can be user ID or server identifier)
            parameters: Additional event parameters
            
        Returns:
            True if successful, False otherwise
        """
        if not self.measurement_id or not self.api_secret:
            logger.debug("Google Analytics not configured, skipping event tracking")
            return False
        
        try:
            # Build the payload according to GA4 Measurement Protocol
            payload = {
                "client_id": client_id,
                "events": [
                    {
                        "name": event_name,
                        "params": parameters or {}
                    }
                ]
            }
            
            # Make the request to Google Analytics
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}?measurement_id={self.measurement_id}&api_secret={self.api_secret}",
                    json=payload,
                    timeout=10.0
                )
                
                if response.status_code == 204:
                    logger.debug(f"Successfully tracked event: {event_name}")
                    return True
                else:
                    logger.warning(f"Failed to track event {event_name}: HTTP {response.status_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error tracking event {event_name}: {e}")
            return False
    
    async def track_api_failure(self,
                               endpoint: str,
                               error_code: int,
                               error_type: str = "model_api_error",
                               user_id: Optional[str] = None) -> bool:
        """Track API failure events to Google Analytics.
        
        Args:
            endpoint: The API endpoint that failed
            error_code: HTTP error code (e.g., 529)
            error_type: Type of error (e.g., "model_overloaded", "model_api_error")
            user_id: Optional user ID for tracking
            
        Returns:
            True if successful, False otherwise
        """
        client_id = user_id if user_id else "backend-server"
        
        parameters = {
            "endpoint": endpoint,
            "error_code": error_code,
            "error_type": error_type,
            "timestamp": asyncio.get_event_loop().time()
        }
        
        return await self.track_event("api_failure", client_id, parameters)
    
    async def track_model_rate_limit(self,
                                     endpoint: str,
                                     user_id: Optional[str] = None) -> bool:
        """Track 429 rate limiting errors reported by the LLM provider.
        
        Args:
            endpoint: The API endpoint that experienced the rate limit
            user_id: Optional user ID for tracking
            
        Returns:
            True if successful, False otherwise
        """
        return await self.track_api_failure(
            endpoint=endpoint,
            error_code=429,
            error_type="model_rate_limited",
            user_id=user_id
        )

    async def track_model_token_usage(self,
                                      endpoint: str,
                                      input_tokens: int,
                                      output_tokens: int,
                                      user_id: Optional[str] = None) -> bool:
        """Track token usage metrics for model invocations.
        
        Args:
            endpoint: The API endpoint that was called
            input_tokens: Number of input tokens used
            output_tokens: Number of output tokens used
            user_id: Optional user ID for tracking
            
        Returns:
            True if successful, False otherwise
        """
        client_id = user_id if user_id else "backend-server"
        
        parameters = {
            "endpoint": endpoint,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "timestamp": asyncio.get_event_loop().time()
        }
        
        return await self.track_event("model_token_usage", client_id, parameters)


# Global instance
_analytics_service = None

def get_analytics_service() -> GoogleAnalyticsService:
    """Get or create the global analytics service instance."""
    global _analytics_service
    if _analytics_service is None:
        _analytics_service = GoogleAnalyticsService()
    return _analytics_service
