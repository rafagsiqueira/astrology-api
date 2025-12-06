"""Service for managing user subscription queries."""

from typing import Optional
from datetime import datetime, timezone
from auth import get_firestore_client
from subscription_models import UserSubscription, SubscriptionStatus, SubscriptionType, AppStoreEnvironment, PRODUCT_ID_MAPPINGS
from google.cloud.firestore import FieldFilter
from appstoreserverlibrary.models.JWSTransactionDecodedPayload import JWSTransactionDecodedPayload
from appstoreserverlibrary.models.NotificationTypeV2 import NotificationTypeV2
from appstoreserverlibrary.models.Subtype import Subtype
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

    async def update_subscription_from_transaction(
        self, 
        transaction_info: JWSTransactionDecodedPayload, 
        notification_type: Optional[NotificationTypeV2] = None, 
        subtype: Optional[Subtype] = None
    ) -> bool:
        """
        Update user subscription in Firestore based on transaction info.
        
        Args:
            transaction_info: Decoded transaction payload from App Store
            notification_type: Optional notification type triggering this update
            subtype: Optional notification subtype
            
        Returns:
            True if update was successful, False otherwise
        """
        try:
            db = get_firestore_client()
            if not db:
                logger.error("Firestore client not available")
                return False

            original_transaction_id = transaction_info.originalTransactionId
            
            # Find user associated with this original transaction ID
            user_id = None
            
            # First check if we already have a subscription with this original_transaction_id
            subscriptions_query = db.collection('subscriptions').where(
                filter=FieldFilter('original_transaction_id', '==', original_transaction_id)
            ).limit(1)
            
            docs = subscriptions_query.get()
            for doc in docs:
                subscription_data = doc.to_dict()
                user_id = subscription_data.get('user_id')
                break
            
            # If not found via existing subscription, check the transaction's appAccountToken
            if not user_id:
                if hasattr(transaction_info, 'appAccountToken') and transaction_info.appAccountToken:
                     user_id = transaction_info.appAccountToken
                     logger.info(f"User ID {user_id} found in appAccountToken for {original_transaction_id}")
            
            if not user_id:
                logger.warning(f"No user found for original transaction ID: {original_transaction_id}")
                # In a real scenario, we might want to create a dangling subscription record 
                # or log this for manual review if it's an INITIAL_BUY notification 
                # but we don't know the user yet (e.g. if the app hasn't sent the receipt yet).
                # For now, we can't update a user's subscription if we don't know who they are.
                return False

            # Determine subscription status and type
            product_id = transaction_info.productId
            subscription_type = PRODUCT_ID_MAPPINGS.get(product_id, SubscriptionType.MONTHLY)
            
            # Default status
            status = SubscriptionStatus.ACTIVE
            
            # Handle expiration
            expires_date_ms = transaction_info.expiresDate
            if expires_date_ms:
                expires_date = datetime.fromtimestamp(expires_date_ms / 1000, tz=timezone.utc)
                if expires_date < datetime.now(timezone.utc):
                    status = SubscriptionStatus.EXPIRED
            else:
                expires_date = None

            # Handle specific notification types/subtypes logic
            if notification_type == NotificationTypeV2.DID_RENEW:
                status = SubscriptionStatus.ACTIVE
            elif notification_type == NotificationTypeV2.EXPIRED: # Note: V2 uses EXPIRED
                status = SubscriptionStatus.EXPIRED
            elif notification_type == NotificationTypeV2.DID_FAIL_TO_RENEW:
                status = SubscriptionStatus.BILLING_RETRY
                # You might want to check is_in_billing_retry_period from renewal info if available
            
            # Create or update subscription object
            subscription = UserSubscription(
                user_id=user_id,
                subscription_type=subscription_type,
                subscription_status=status,
                original_transaction_id=original_transaction_id,
                current_transaction_id=transaction_info.transactionId,
                product_id=product_id,
                purchase_date=datetime.fromtimestamp(transaction_info.purchaseDate / 1000, tz=timezone.utc),
                expires_date=expires_date,
                environment=AppStoreEnvironment.SANDBOX if transaction_info.environment == "Sandbox" else AppStoreEnvironment.PRODUCTION,
                updated_at=datetime.now(timezone.utc)
            )
            
            # Update Firestore
            # We use the original_transaction_id as a stable key or query by it. 
            # Since we found the doc above, we can update it.
            # But wait, a user might have multiple subscriptions? 
            # Usually one active subscription per group.
            # Let's update the specific document we found or create a new one if logic dictates.
            # Ideally we update the document corresponding to this original_transaction_id.
            
            # Re-query to get the doc ref (or use the one from above if we kept it)
            # We'll just add/merge the data.
            
            # Using a composite ID or just auto-id? 
            # The previous code seemed to query by user_id. 
            # Let's assume we update the document found.
            
            if docs:
                doc_ref = docs[0].reference
                doc_ref.set(subscription.to_firestore_dict(), merge=True)
                logger.info(f"Updated subscription for user {user_id} (Original Tx: {original_transaction_id})")
            else:
                 # New subscription for this original_transaction_id
                 db.collection('subscriptions').add(subscription.to_firestore_dict())
                 logger.info(f"Created new subscription for user {user_id} (Original Tx: {original_transaction_id})")
                
            return True

        except Exception as e:
            logger.error(f"Error updating subscription from transaction: {e}")
            return False


# Global instance
_subscription_service = None


def get_subscription_service() -> SubscriptionService:
    """Get or create the global subscription service instance."""
    global _subscription_service
    if _subscription_service is None:
        _subscription_service = SubscriptionService()
    return _subscription_service