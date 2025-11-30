"""App Store Server notifications handler."""

import json
import jwt
import base64
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
import httpx

from subscription_models import (
    AppStoreNotification, NotificationData, TransactionInfo, RenewalInfo,
    NotificationType, SubscriptionType, SubscriptionStatus, UserSubscription,
    AppStoreEnvironment, PRODUCT_ID_MAPPINGS
)
from subscription_analytics import get_subscription_analytics_service
from auth import get_firestore_client
from google.cloud.firestore import FieldFilter
from config import get_logger

logger = get_logger(__name__)


class AppStoreNotificationHandler:
    """Handler for App Store Server notifications."""
    
    def __init__(self):
        self.analytics = get_subscription_analytics_service()
        self.apple_keys_cache = {}
        self.apple_keys_url = "https://appleid.apple.com/auth/keys"
    
    async def fetch_apple_public_keys(self) -> Dict[str, Any]:
        """Fetch Apple's public keys for JWT verification."""
        try:
            if self.apple_keys_cache:
                return self.apple_keys_cache
            
            async with httpx.AsyncClient() as client:
                response = await client.get(self.apple_keys_url)
                response.raise_for_status()
                
                keys_data = response.json()
                self.apple_keys_cache = keys_data
                logger.info("Successfully fetched Apple public keys")
                return keys_data
                
        except Exception as e:
            logger.error(f"Failed to fetch Apple public keys: {e}")
            raise
    
    def get_public_key_from_jwks(self, kid: str, jwks: Dict[str, Any]) -> rsa.RSAPublicKey:
        """Extract RSA public key from JWKS for given key ID."""
        for key_data in jwks.get("keys", []):
            if key_data.get("kid") == kid:
                # Convert JWK to RSA public key
                n = int.from_bytes(
                    base64.urlsafe_b64decode(key_data["n"] + "=="), 
                    byteorder="big"
                )
                e = int.from_bytes(
                    base64.urlsafe_b64decode(key_data["e"] + "=="), 
                    byteorder="big"
                )
                
                public_numbers = rsa.RSAPublicNumbers(e, n)
                return public_numbers.public_key(backend=default_backend())
        
        raise ValueError(f"Key ID {kid} not found in JWKS")
    
    async def verify_and_decode_jwt(self, signed_payload: str) -> Dict[str, Any]:
        """Verify and decode Apple's signed JWT payload."""
        try:
            # Decode header to get key ID
            header = jwt.get_unverified_header(signed_payload)
            kid = header.get("kid")
            
            if not kid:
                raise ValueError("No key ID found in JWT header")
            
            # Fetch Apple's public keys
            jwks = await self.fetch_apple_public_keys()
            
            # Get the public key for verification
            public_key = self.get_public_key_from_jwks(kid, jwks)
            
            # Verify and decode the JWT
            payload = jwt.decode(
                signed_payload,
                public_key,
                algorithms=["RS256"],
                options={"verify_exp": True}
            )
            
            logger.debug("Successfully verified and decoded JWT payload")
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.error("JWT signature has expired")
            raise
        except jwt.InvalidTokenError as e:
            logger.error(f"Invalid JWT token: {e}")
            raise
        except Exception as e:
            logger.error(f"Error verifying JWT: {e}")
            raise
    
    def get_subscription_type_from_product_id(self, product_id: str) -> SubscriptionType:
        """Get subscription type from product ID."""
        subscription_type = PRODUCT_ID_MAPPINGS.get(product_id)
        if not subscription_type:
            logger.warning(f"Unknown product ID: {product_id}")
            # Default to monthly if we can't determine
            return SubscriptionType.MONTHLY
        return subscription_type
    
    def timestamp_to_datetime(self, timestamp: int) -> datetime:
        """Convert timestamp to datetime object."""
        return datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)
    
    async def find_user_by_original_transaction_id(self, original_transaction_id: str) -> Optional[str]:
        """Find user ID by original transaction ID."""
        try:
            db = get_firestore_client()
            if not db:
                logger.error("Firestore client not available")
                return None
            
            # Query subscriptions collection for this original transaction ID
            subscriptions_query = db.collection('subscriptions').where(
                filter=FieldFilter('original_transaction_id', '==', original_transaction_id)
            ).limit(1)
            
            docs = subscriptions_query.get()
            for doc in docs:
                subscription_data = doc.to_dict()
                return subscription_data.get('user_id')
            
            logger.warning(f"No user found for original transaction ID: {original_transaction_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error finding user by transaction ID: {e}")
            return None
    
    async def update_user_subscription(self, user_id: str, subscription: UserSubscription) -> bool:
        """Update user's subscription status in Firestore."""
        try:
            db = get_firestore_client()
            if not db:
                logger.error("Firestore client not available")
                return False
            
            # Store subscription in dedicated subscriptions collection
            # Use original_transaction_id as document ID for easy lookups
            subscription_ref = db.collection('subscriptions').document(subscription.original_transaction_id)
            subscription_data = subscription.to_firestore_dict()
            
            # Use set() to create or update the subscription document
            subscription_ref.set(subscription_data)
            
            logger.info(f"Updated subscription for user {user_id}: {subscription.subscription_status}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating user subscription: {e}")
            return False
    
    async def handle_initial_buy(self, notification: AppStoreNotification, transaction_info: TransactionInfo) -> bool:
        """Handle INITIAL_BUY notification."""
        try:
            # For initial buy, we need to find the user somehow
            # This might require additional logic based on your user identification strategy
            user_id = await self.find_user_by_original_transaction_id(transaction_info.original_transaction_id)
            
            if not user_id:
                logger.warning(f"Cannot handle INITIAL_BUY: user not found for transaction {transaction_info.original_transaction_id}")
                return False
            
            subscription_type = self.get_subscription_type_from_product_id(transaction_info.product_id)
            
            # Determine subscription status based on type
            if subscription_type == SubscriptionType.LIFETIME:
                subscription_status = SubscriptionStatus.LIFETIME
            else:
                subscription_status = SubscriptionStatus.ACTIVE
            
            # Create subscription record
            subscription = UserSubscription(
                user_id=user_id,
                subscription_type=subscription_type,
                subscription_status=subscription_status,
                original_transaction_id=transaction_info.original_transaction_id,
                current_transaction_id=transaction_info.transaction_id,
                product_id=transaction_info.product_id,
                purchase_date=self.timestamp_to_datetime(transaction_info.purchase_date),
                expires_date=self.timestamp_to_datetime(transaction_info.expires_date) if transaction_info.expires_date else None,
                environment=transaction_info.environment
            )
            
            # Update user subscription
            await self.update_user_subscription(user_id, subscription)
            
            # Track analytics
            if subscription_type == SubscriptionType.LIFETIME:
                await self.analytics.track_lifetime_purchase(
                    user_id=user_id,
                    transaction_id=transaction_info.transaction_id,
                    product_id=transaction_info.product_id,
                    environment=transaction_info.environment,
                    revenue=transaction_info.price / 1000000 if transaction_info.price else None,  # Price is in microunits
                    currency=transaction_info.currency
                )
            else:
                await self.analytics.track_initial_purchase(
                    user_id=user_id,
                    transaction_id=transaction_info.transaction_id,
                    product_id=transaction_info.product_id,
                    subscription_type=subscription_type,
                    environment=transaction_info.environment,
                    revenue=transaction_info.price / 1000000 if transaction_info.price else None,
                    currency=transaction_info.currency
                )
            
            logger.info(f"Handled INITIAL_BUY for user {user_id}, product {transaction_info.product_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error handling INITIAL_BUY notification: {e}")
            return False
    
    async def handle_did_renew(self, notification: AppStoreNotification, transaction_info: TransactionInfo) -> bool:
        """Handle DID_RENEW notification."""
        try:
            user_id = await self.find_user_by_original_transaction_id(transaction_info.original_transaction_id)
            if not user_id:
                logger.warning(f"Cannot handle DID_RENEW: user not found for transaction {transaction_info.original_transaction_id}")
                return False
            
            subscription_type = self.get_subscription_type_from_product_id(transaction_info.product_id)
            
            # Update subscription with new transaction and expiry
            subscription = UserSubscription(
                user_id=user_id,
                subscription_type=subscription_type,
                subscription_status=SubscriptionStatus.ACTIVE,
                original_transaction_id=transaction_info.original_transaction_id,
                current_transaction_id=transaction_info.transaction_id,
                product_id=transaction_info.product_id,
                purchase_date=self.timestamp_to_datetime(transaction_info.original_purchase_date),
                expires_date=self.timestamp_to_datetime(transaction_info.expires_date) if transaction_info.expires_date else None,
                environment=transaction_info.environment,
                is_in_billing_retry=False,
                grace_period_expires_date=None
            )
            
            await self.update_user_subscription(user_id, subscription)
            
            # Track renewal analytics
            await self.analytics.track_renewal(
                user_id=user_id,
                transaction_id=transaction_info.transaction_id,
                product_id=transaction_info.product_id,
                subscription_type=subscription_type,
                environment=transaction_info.environment,
                revenue=transaction_info.price / 1000000 if transaction_info.price else None,
                currency=transaction_info.currency
            )
            
            logger.info(f"Handled DID_RENEW for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error handling DID_RENEW notification: {e}")
            return False
    
    async def handle_cancel(self, notification: AppStoreNotification, transaction_info: TransactionInfo) -> bool:
        """Handle CANCEL notification."""
        try:
            user_id = await self.find_user_by_original_transaction_id(transaction_info.original_transaction_id)
            if not user_id:
                logger.warning(f"Cannot handle CANCEL: user not found for transaction {transaction_info.original_transaction_id}")
                return False
            
            subscription_type = self.get_subscription_type_from_product_id(transaction_info.product_id)
            
            # Update subscription to expired status
            subscription = UserSubscription(
                user_id=user_id,
                subscription_type=subscription_type,
                subscription_status=SubscriptionStatus.EXPIRED,
                original_transaction_id=transaction_info.original_transaction_id,
                current_transaction_id=transaction_info.transaction_id,
                product_id=transaction_info.product_id,
                purchase_date=self.timestamp_to_datetime(transaction_info.original_purchase_date),
                expires_date=self.timestamp_to_datetime(transaction_info.expires_date) if transaction_info.expires_date else None,
                environment=transaction_info.environment,
                auto_renew_enabled=False
            )
            
            await self.update_user_subscription(user_id, subscription)
            
            # Track cancellation analytics
            await self.analytics.track_cancellation(
                user_id=user_id,
                transaction_id=transaction_info.transaction_id,
                product_id=transaction_info.product_id,
                subscription_type=subscription_type,
                environment=transaction_info.environment,
                is_voluntary=True
            )
            
            logger.info(f"Handled CANCEL for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error handling CANCEL notification: {e}")
            return False
    
    async def handle_did_fail_to_renew(self, notification: AppStoreNotification, transaction_info: TransactionInfo, renewal_info: Optional[RenewalInfo] = None) -> bool:
        """Handle DID_FAIL_TO_RENEW notification."""
        try:
            user_id = await self.find_user_by_original_transaction_id(transaction_info.original_transaction_id)
            if not user_id:
                logger.warning(f"Cannot handle DID_FAIL_TO_RENEW: user not found for transaction {transaction_info.original_transaction_id}")
                return False
            
            subscription_type = self.get_subscription_type_from_product_id(transaction_info.product_id)
            
            # Check if in billing retry period
            is_in_billing_retry = False
            grace_period_expires = None
            
            if renewal_info:
                is_in_billing_retry = renewal_info.is_in_billing_retry_period or False
                if renewal_info.grace_period_expires_date:
                    grace_period_expires = self.timestamp_to_datetime(renewal_info.grace_period_expires_date)
            
            # Determine status based on billing retry
            if is_in_billing_retry:
                subscription_status = SubscriptionStatus.BILLING_RETRY
            elif grace_period_expires:
                subscription_status = SubscriptionStatus.GRACE_PERIOD
            else:
                subscription_status = SubscriptionStatus.EXPIRED
            
            subscription = UserSubscription(
                user_id=user_id,
                subscription_type=subscription_type,
                subscription_status=subscription_status,
                original_transaction_id=transaction_info.original_transaction_id,
                current_transaction_id=transaction_info.transaction_id,
                product_id=transaction_info.product_id,
                purchase_date=self.timestamp_to_datetime(transaction_info.original_purchase_date),
                expires_date=self.timestamp_to_datetime(transaction_info.expires_date) if transaction_info.expires_date else None,
                environment=transaction_info.environment,
                is_in_billing_retry=is_in_billing_retry,
                grace_period_expires_date=grace_period_expires
            )
            
            await self.update_user_subscription(user_id, subscription)
            
            # Track failed renewal analytics
            await self.analytics.track_failed_renewal(
                user_id=user_id,
                transaction_id=transaction_info.transaction_id,
                product_id=transaction_info.product_id,
                subscription_type=subscription_type,
                environment=transaction_info.environment,
                is_in_billing_retry=is_in_billing_retry
            )
            
            logger.info(f"Handled DID_FAIL_TO_RENEW for user {user_id}, billing retry: {is_in_billing_retry}")
            return True
            
        except Exception as e:
            logger.error(f"Error handling DID_FAIL_TO_RENEW notification: {e}")
            return False
    
    async def handle_did_recover(self, notification: AppStoreNotification, transaction_info: TransactionInfo) -> bool:
        """Handle DID_RECOVER notification."""
        try:
            user_id = await self.find_user_by_original_transaction_id(transaction_info.original_transaction_id)
            if not user_id:
                logger.warning(f"Cannot handle DID_RECOVER: user not found for transaction {transaction_info.original_transaction_id}")
                return False
            
            subscription_type = self.get_subscription_type_from_product_id(transaction_info.product_id)
            
            # Restore active subscription
            subscription = UserSubscription(
                user_id=user_id,
                subscription_type=subscription_type,
                subscription_status=SubscriptionStatus.ACTIVE,
                original_transaction_id=transaction_info.original_transaction_id,
                current_transaction_id=transaction_info.transaction_id,
                product_id=transaction_info.product_id,
                purchase_date=self.timestamp_to_datetime(transaction_info.original_purchase_date),
                expires_date=self.timestamp_to_datetime(transaction_info.expires_date) if transaction_info.expires_date else None,
                environment=transaction_info.environment,
                is_in_billing_retry=False,
                grace_period_expires_date=None
            )
            
            await self.update_user_subscription(user_id, subscription)
            
            # Track recovery analytics
            await self.analytics.track_recovery(
                user_id=user_id,
                transaction_id=transaction_info.transaction_id,
                product_id=transaction_info.product_id,
                subscription_type=subscription_type,
                environment=transaction_info.environment,
                revenue=transaction_info.price / 1000000 if transaction_info.price else None,
                currency=transaction_info.currency
            )
            
            logger.info(f"Handled DID_RECOVER for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error handling DID_RECOVER notification: {e}")
            return False
    
    async def handle_refund(self, notification: AppStoreNotification, transaction_info: TransactionInfo) -> bool:
        """Handle REFUND notification."""
        try:
            user_id = await self.find_user_by_original_transaction_id(transaction_info.original_transaction_id)
            if not user_id:
                logger.warning(f"Cannot handle REFUND: user not found for transaction {transaction_info.original_transaction_id}")
                return False
            
            subscription_type = self.get_subscription_type_from_product_id(transaction_info.product_id)
            
            # Set subscription to revoked status
            subscription = UserSubscription(
                user_id=user_id,
                subscription_type=subscription_type,
                subscription_status=SubscriptionStatus.REVOKED,
                original_transaction_id=transaction_info.original_transaction_id,
                current_transaction_id=transaction_info.transaction_id,
                product_id=transaction_info.product_id,
                purchase_date=self.timestamp_to_datetime(transaction_info.original_purchase_date),
                expires_date=None,  # Revoked subscriptions don't have expiry dates
                environment=transaction_info.environment,
                auto_renew_enabled=False
            )
            
            await self.update_user_subscription(user_id, subscription)
            
            # Track refund analytics
            await self.analytics.track_refund(
                user_id=user_id,
                transaction_id=transaction_info.transaction_id,
                product_id=transaction_info.product_id,
                subscription_type=subscription_type,
                environment=transaction_info.environment,
                refund_amount=transaction_info.price / 1000000 if transaction_info.price else None,
                currency=transaction_info.currency
            )
            
            logger.info(f"Handled REFUND for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error handling REFUND notification: {e}")
            return False
    
    async def handle_grace_period_expired(self, notification: AppStoreNotification, transaction_info: TransactionInfo) -> bool:
        """Handle GRACE_PERIOD_EXPIRED notification."""
        try:
            user_id = await self.find_user_by_original_transaction_id(transaction_info.original_transaction_id)
            if not user_id:
                logger.warning(f"Cannot handle GRACE_PERIOD_EXPIRED: user not found for transaction {transaction_info.original_transaction_id}")
                return False
            
            subscription_type = self.get_subscription_type_from_product_id(transaction_info.product_id)
            
            # Set subscription to expired
            subscription = UserSubscription(
                user_id=user_id,
                subscription_type=subscription_type,
                subscription_status=SubscriptionStatus.EXPIRED,
                original_transaction_id=transaction_info.original_transaction_id,
                current_transaction_id=transaction_info.transaction_id,
                product_id=transaction_info.product_id,
                purchase_date=self.timestamp_to_datetime(transaction_info.original_purchase_date),
                expires_date=self.timestamp_to_datetime(transaction_info.expires_date) if transaction_info.expires_date else None,
                environment=transaction_info.environment,
                grace_period_expires_date=None
            )
            
            await self.update_user_subscription(user_id, subscription)
            
            # Track grace period expiration analytics
            await self.analytics.track_grace_period_expired(
                user_id=user_id,
                transaction_id=transaction_info.transaction_id,
                product_id=transaction_info.product_id,
                subscription_type=subscription_type,
                environment=transaction_info.environment
            )
            
            logger.info(f"Handled GRACE_PERIOD_EXPIRED for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error handling GRACE_PERIOD_EXPIRED notification: {e}")
            return False
    
    async def process_notification(self, signed_payload: str) -> Tuple[bool, str]:
        """Process an App Store Server notification."""
        try:
            # Verify and decode the main notification payload
            notification_payload = await self.verify_and_decode_jwt(signed_payload)
            notification = AppStoreNotification(**notification_payload)
            
            logger.info(f"Processing notification: {notification.notification_type} for {notification.data.bundle_id}")
            
            # Decode the transaction info
            transaction_payload = await self.verify_and_decode_jwt(notification.data.signed_transaction_info)
            transaction_info = TransactionInfo(**transaction_payload)
            
            # Decode renewal info if present
            renewal_info = None
            if notification.data.signed_renewal_info:
                renewal_payload = await self.verify_and_decode_jwt(notification.data.signed_renewal_info)
                renewal_info = RenewalInfo(**renewal_payload)
            
            # Route to appropriate handler based on notification type
            success = False
            
            if notification.notification_type == NotificationType.INITIAL_BUY:
                success = await self.handle_initial_buy(notification, transaction_info)
            
            elif notification.notification_type == NotificationType.DID_RENEW:
                success = await self.handle_did_renew(notification, transaction_info)
            
            elif notification.notification_type == NotificationType.CANCEL:
                success = await self.handle_cancel(notification, transaction_info)
            
            elif notification.notification_type == NotificationType.DID_FAIL_TO_RENEW:
                success = await self.handle_did_fail_to_renew(notification, transaction_info, renewal_info)
            
            elif notification.notification_type == NotificationType.DID_RECOVER:
                success = await self.handle_did_recover(notification, transaction_info)
            
            elif notification.notification_type == NotificationType.REFUND:
                success = await self.handle_refund(notification, transaction_info)
            
            elif notification.notification_type == NotificationType.GRACE_PERIOD_EXPIRED:
                success = await self.handle_grace_period_expired(notification, transaction_info)
            
            else:
                logger.info(f"Unhandled notification type: {notification.notification_type}")
                return True, f"Notification type {notification.notification_type} not handled"
            
            if success:
                return True, f"Successfully processed {notification.notification_type}"
            else:
                return False, f"Failed to process {notification.notification_type}"
            
        except Exception as e:
            error_msg = f"Error processing notification: {e}"
            logger.error(error_msg)
            return False, error_msg


# Global instance
_notification_handler = None


def get_notification_handler() -> AppStoreNotificationHandler:
    """Get or create the global notification handler instance."""
    global _notification_handler
    if _notification_handler is None:
        _notification_handler = AppStoreNotificationHandler()
    return _notification_handler