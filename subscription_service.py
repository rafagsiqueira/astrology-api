"""Service for managing user subscription queries."""

from typing import Optional
from datetime import datetime, timezone
from auth import get_firestore_client
from subscription_models import UserSubscription, SubscriptionStatus, SubscriptionType
from google.cloud.firestore import FieldFilter
from config import get_logger

logger = get_logger(__name__)


class SubscriptionService:
    """Service for querying user subscription information."""
    
    def __init__(self):
        pass
    
    async def get_user_subscription(self, user_id: str) -> Optional[UserSubscription]:
        """Get user's current subscription status."""
        try:
            db = get_firestore_client()
            if not db:
                logger.error("Firestore client not available")
                return None
            
            # Query subscriptions collection for this user
            subscriptions_query = db.collection('subscriptions').where(
                filter=FieldFilter('user_id', '==', user_id)
            ).order_by('created_at', direction='DESCENDING').limit(1)
            
            docs = subscriptions_query.get()
            for doc in docs:
                subscription_data = doc.to_dict()
                
                # Convert Firestore timestamps back to datetime objects
                if subscription_data and 'purchase_date' in subscription_data and subscription_data['purchase_date']:
                    subscription_data['purchase_date'] = subscription_data['purchase_date'].replace(tzinfo=timezone.utc)
                if subscription_data and 'expires_date' in subscription_data and subscription_data['expires_date']:
                    subscription_data['expires_date'] = subscription_data['expires_date'].replace(tzinfo=timezone.utc)
                if subscription_data and 'grace_period_expires_date' in subscription_data and subscription_data['grace_period_expires_date']:
                    subscription_data['grace_period_expires_date'] = subscription_data['grace_period_expires_date'].replace(tzinfo=timezone.utc)
                if subscription_data and 'created_at' in subscription_data and subscription_data['created_at']:
                    subscription_data['created_at'] = subscription_data['created_at'].replace(tzinfo=timezone.utc)
                if subscription_data and 'updated_at' in subscription_data and subscription_data['updated_at']:
                    subscription_data['updated_at'] = subscription_data['updated_at'].replace(tzinfo=timezone.utc)
                
                # Convert string enums back to enum objects
                if subscription_data and 'subscription_type' in subscription_data:
                    subscription_data['subscription_type'] = SubscriptionType(subscription_data['subscription_type'])
                if subscription_data and 'subscription_status' in subscription_data:
                    subscription_data['subscription_status'] = SubscriptionStatus(subscription_data['subscription_status'])
                if subscription_data and 'environment' in subscription_data:
                    from subscription_models import AppStoreEnvironment
                    subscription_data['environment'] = AppStoreEnvironment(subscription_data['environment'])
                
                if subscription_data:
                    return UserSubscription(**subscription_data)
            
            logger.debug(f"No subscription found for user: {user_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting user subscription: {e}")
            return None
    
    async def is_user_subscribed(self, user_id: str) -> bool:
        """Check if user has an active subscription (including lifetime)."""
        subscription = await self.get_user_subscription(user_id)
        if not subscription:
            return False
        
        active_statuses = {
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.GRACE_PERIOD,
            SubscriptionStatus.BILLING_RETRY,
            SubscriptionStatus.LIFETIME
        }
        
        return subscription.subscription_status in active_statuses
    
    async def has_premium_access(self, user_id: str) -> bool:
        """
        Check if user has premium access (active subscription or lifetime).
        This is the main method for backend API authorization.
        """
        try:
            subscription = await self.get_user_subscription(user_id)
            if not subscription:
                return False
            
            # Check for lifetime access
            if subscription.subscription_status == SubscriptionStatus.LIFETIME:
                return True
            
            # Check for active subscription statuses
            if subscription.subscription_status not in {
                SubscriptionStatus.ACTIVE,
                SubscriptionStatus.GRACE_PERIOD,
                SubscriptionStatus.BILLING_RETRY
            }:
                return False
            
            # For time-limited subscriptions, check expiry
            if subscription.expires_date:
                now = datetime.now(timezone.utc)
                
                # If past expiry date
                if now > subscription.expires_date:
                    # Check if still in grace period
                    if (subscription.grace_period_expires_date and 
                        now <= subscription.grace_period_expires_date):
                        return True  # Still in grace period
                    else:
                        return False  # Truly expired
            
            return True  # Active subscription
            
        except Exception as e:
            logger.error(f"Error checking premium access for user {user_id}: {e}")
            return False


# Global instance
_subscription_service = None


def get_subscription_service() -> SubscriptionService:
    """Get or create the global subscription service instance."""
    global _subscription_service
    if _subscription_service is None:
        _subscription_service = SubscriptionService()
    return _subscription_service