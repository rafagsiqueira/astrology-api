"""App Store Server notifications handler."""

from typing import Optional
from fastapi import Request, HTTPException
from appstoreserverlibrary.models.NotificationTypeV2 import NotificationTypeV2
from appstoreserverlibrary.models.Subtype import Subtype
from subscription_verifier import SubscriptionVerifier
from subscription_service import get_subscription_service
from config import get_logger

logger = get_logger(__name__)

class AppStoreNotificationHandler:
    """Handler for App Store Server notifications."""
    
    def __init__(self):
        self.verifier = SubscriptionVerifier().get_verifier()
        self.subscription_service = get_subscription_service()
    
    async def handle_notification(self, request: Request):
        """Handle incoming App Store Server notification."""
        if not self.verifier:
            logger.error("Verifier not initialized")
            raise HTTPException(status_code=500, detail="Server configuration error")
            
        try:
            # Get the signed payload from the request body
            body = await request.json()
            signed_payload = body.get("signedPayload")
            
            if not signed_payload:
                logger.error("No signedPayload in request")
                raise HTTPException(status_code=400, detail="Missing signedPayload")
            
            # Verify and decode the notification
            notification = self.verifier.verify_and_decode_notification(signed_payload)
            
            logger.info(f"Received notification: {notification.notificationType} (Subtype: {notification.subtype})")
            
            # Extract transaction info if available
            if notification.data and notification.data.signedTransactionInfo:
                transaction_info = self.verifier.verify_and_decode_transaction(notification.data.signedTransactionInfo)
                
                # Update subscription based on notification type
                await self.subscription_service.update_subscription_from_transaction(
                    transaction_info,
                    notification_type=notification.notificationType,
                    subtype=notification.subtype
                )
                
            return {"status": "success"}
            
        except Exception as e:
            logger.error(f"Error handling notification: {e}")
            raise HTTPException(status_code=500, detail=f"Error processing notification: {str(e)}")

# Global instance
_notification_handler = None

def get_notification_handler() -> AppStoreNotificationHandler:
    """Get or create global notification handler instance."""
    global _notification_handler
    if _notification_handler is None:
        _notification_handler = AppStoreNotificationHandler()
    return _notification_handler