"""Analytics service for subscription events."""

from typing import Optional, Dict, Any
from datetime import datetime
from analytics_service import get_analytics_service
from subscription_models import (
    NotificationType, SubscriptionType, AppStoreEnvironment,
    SubscriptionAnalyticsEvent, UserSubscription
)
from config import get_logger

logger = get_logger(__name__)


class SubscriptionAnalyticsService:
    """Service for tracking subscription-related analytics events."""
    
    def __init__(self):
        self.analytics = get_analytics_service()
    
    async def track_subscription_event(
        self,
        event: SubscriptionAnalyticsEvent
    ) -> bool:
        """Track a subscription analytics event to Google Analytics."""
        try:
            # Prepare event parameters for GA4
            parameters = {
                "transaction_id": event.transaction_id,
                "product_id": event.product_id,
                "subscription_type": event.subscription_type.value,
                "environment": event.environment.value,
                "timestamp": event.timestamp.isoformat(),
            }
            
            # Add revenue information if available
            if event.revenue is not None:
                parameters["value"] = event.revenue
                parameters["currency"] = event.currency or "USD"
            
            # Add notification type if provided
            if event.notification_type:
                parameters["notification_type"] = event.notification_type.value
            
            # Merge additional properties
            parameters.update(event.properties)
            
            # Track the event
            success = await self.analytics.track_event(
                event_name=event.event_name,
                client_id=event.user_id,
                parameters=parameters
            )
            
            if success:
                logger.info(f"Tracked subscription event: {event.event_name} for user: {event.user_id}")
            else:
                logger.warning(f"Failed to track subscription event: {event.event_name} for user: {event.user_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error tracking subscription event {event.event_name}: {e}")
            return False
    
    async def track_initial_purchase(
        self,
        user_id: str,
        transaction_id: str,
        product_id: str,
        subscription_type: SubscriptionType,
        environment: AppStoreEnvironment,
        revenue: Optional[float] = None,
        currency: Optional[str] = None
    ) -> bool:
        """Track initial subscription purchase."""
        event = SubscriptionAnalyticsEvent(
            event_name="subscription_started",
            user_id=user_id,
            transaction_id=transaction_id,
            product_id=product_id,
            subscription_type=subscription_type,
            environment=environment,
            revenue=revenue,
            currency=currency,
            notification_type=NotificationType.INITIAL_BUY,
            properties={
                "is_trial": False,  # Adjust based on your trial logic
                "subscription_tier": subscription_type.value,
            }
        )
        return await self.track_subscription_event(event)
    
    async def track_renewal(
        self,
        user_id: str,
        transaction_id: str,
        product_id: str,
        subscription_type: SubscriptionType,
        environment: AppStoreEnvironment,
        revenue: Optional[float] = None,
        currency: Optional[str] = None
    ) -> bool:
        """Track subscription renewal."""
        event = SubscriptionAnalyticsEvent(
            event_name="subscription_renewed",
            user_id=user_id,
            transaction_id=transaction_id,
            product_id=product_id,
            subscription_type=subscription_type,
            environment=environment,
            revenue=revenue,
            currency=currency,
            notification_type=NotificationType.DID_RENEW,
            properties={
                "renewal_type": "automatic",
            }
        )
        return await self.track_subscription_event(event)
    
    async def track_cancellation(
        self,
        user_id: str,
        transaction_id: str,
        product_id: str,
        subscription_type: SubscriptionType,
        environment: AppStoreEnvironment,
        is_voluntary: bool = True
    ) -> bool:
        """Track subscription cancellation."""
        event = SubscriptionAnalyticsEvent(
            event_name="subscription_cancelled",
            user_id=user_id,
            transaction_id=transaction_id,
            product_id=product_id,
            subscription_type=subscription_type,
            environment=environment,
            notification_type=NotificationType.CANCEL,
            properties={
                "cancellation_type": "voluntary" if is_voluntary else "involuntary",
                "subscription_tier": subscription_type.value,
            }
        )
        return await self.track_subscription_event(event)
    
    async def track_failed_renewal(
        self,
        user_id: str,
        transaction_id: str,
        product_id: str,
        subscription_type: SubscriptionType,
        environment: AppStoreEnvironment,
        is_in_billing_retry: bool = False
    ) -> bool:
        """Track failed subscription renewal."""
        event = SubscriptionAnalyticsEvent(
            event_name="subscription_failed_renewal",
            user_id=user_id,
            transaction_id=transaction_id,
            product_id=product_id,
            subscription_type=subscription_type,
            environment=environment,
            notification_type=NotificationType.DID_FAIL_TO_RENEW,
            properties={
                "is_in_billing_retry": is_in_billing_retry,
                "subscription_tier": subscription_type.value,
            }
        )
        return await self.track_subscription_event(event)
    
    async def track_recovery(
        self,
        user_id: str,
        transaction_id: str,
        product_id: str,
        subscription_type: SubscriptionType,
        environment: AppStoreEnvironment,
        revenue: Optional[float] = None,
        currency: Optional[str] = None
    ) -> bool:
        """Track subscription recovery from billing retry."""
        event = SubscriptionAnalyticsEvent(
            event_name="subscription_recovered",
            user_id=user_id,
            transaction_id=transaction_id,
            product_id=product_id,
            subscription_type=subscription_type,
            environment=environment,
            revenue=revenue,
            currency=currency,
            notification_type=NotificationType.DID_RECOVER,
            properties={
                "recovery_type": "billing_retry",
            }
        )
        return await self.track_subscription_event(event)
    
    async def track_refund(
        self,
        user_id: str,
        transaction_id: str,
        product_id: str,
        subscription_type: SubscriptionType,
        environment: AppStoreEnvironment,
        refund_amount: Optional[float] = None,
        currency: Optional[str] = None
    ) -> bool:
        """Track subscription refund."""
        event = SubscriptionAnalyticsEvent(
            event_name="subscription_refunded",
            user_id=user_id,
            transaction_id=transaction_id,
            product_id=product_id,
            subscription_type=subscription_type,
            environment=environment,
            revenue=-refund_amount if refund_amount else None,  # Negative revenue for refunds
            currency=currency,
            notification_type=NotificationType.REFUND,
            properties={
                "refund_amount": refund_amount,
            }
        )
        return await self.track_subscription_event(event)
    
    async def track_lifetime_purchase(
        self,
        user_id: str,
        transaction_id: str,
        product_id: str,
        environment: AppStoreEnvironment,
        revenue: Optional[float] = None,
        currency: Optional[str] = None
    ) -> bool:
        """Track lifetime purchase."""
        event = SubscriptionAnalyticsEvent(
            event_name="lifetime_purchase",
            user_id=user_id,
            transaction_id=transaction_id,
            product_id=product_id,
            subscription_type=SubscriptionType.LIFETIME,
            environment=environment,
            revenue=revenue,
            currency=currency,
            notification_type=NotificationType.INITIAL_BUY,
            properties={
                "purchase_type": "lifetime",
                "subscription_tier": "lifetime",
            }
        )
        return await self.track_subscription_event(event)
    
    async def track_grace_period_expired(
        self,
        user_id: str,
        transaction_id: str,
        product_id: str,
        subscription_type: SubscriptionType,
        environment: AppStoreEnvironment
    ) -> bool:
        """Track grace period expiration."""
        event = SubscriptionAnalyticsEvent(
            event_name="subscription_grace_period_expired",
            user_id=user_id,
            transaction_id=transaction_id,
            product_id=product_id,
            subscription_type=subscription_type,
            environment=environment,
            notification_type=NotificationType.GRACE_PERIOD_EXPIRED,
            properties={
                "subscription_tier": subscription_type.value,
            }
        )
        return await self.track_subscription_event(event)


# Global instance
_subscription_analytics = None


def get_subscription_analytics_service() -> SubscriptionAnalyticsService:
    """Get or create the global subscription analytics service instance."""
    global _subscription_analytics
    if _subscription_analytics is None:
        _subscription_analytics = SubscriptionAnalyticsService()
    return _subscription_analytics