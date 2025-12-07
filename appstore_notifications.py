"""App Store Server notifications handler."""

from typing import Optional
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from appstoreserverlibrary.models.NotificationTypeV2 import NotificationTypeV2
from appstoreserverlibrary.models.Subtype import Subtype
from appstoreserverlibrary.models.Environment import Environment
from appstoreserverlibrary.models.NotificationHistoryRequest import NotificationHistoryRequest
from appstoreserverlibrary.models.NotificationHistoryResponse import NotificationHistoryResponse
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
            
            await self.process_signed_payload(signed_payload)
                
            return JSONResponse(content={"status": "success"}, status_code=200)
            
        except Exception as e:
            logger.error(f"Error handling notification: {e}")
            raise HTTPException(status_code=500, detail=f"Error processing notification: {str(e)}")

    async def process_signed_payload(self, signed_payload: str):
        """Process a signed notification payload."""
        try:
             # Verify and decode the notification
            notification = self.verifier.verify_and_decode_notification(signed_payload)
            
            logger.info(f"Processing notification: {notification.notificationType} (Subtype: {notification.subtype})")
            
            # Extract transaction info if available
            if notification.data and notification.data.signedTransactionInfo:
                transaction_info = self.verifier.verify_and_decode_signed_transaction(notification.data.signedTransactionInfo)
                
                # Update subscription based on notification type
                await self.subscription_service.update_subscription_from_transaction(
                    transaction_info,
                    notification_type=notification.notificationType,
                    subtype=notification.subtype
                )
                
        except Exception as e:
            logger.error(f"Error processing payload: {e}")
            raise

    async def fetch_missed_notifications(self):
        """Fetch and process the latest notification history from App Store."""
        logger.info("Fetching missed notifications from App Store...")
        
        # Access the API client from the verifier's wrapper
        # Note: verifier property on this class is the SignedDataVerifier, 
        # but we need the SubscriptionVerifier instance to get the client.
        # So we need to instantiate SubscriptionVerifier to access the client 
        # or change how we access it. 
        # However, SubscriptionVerifier() creates a new instance each time in the current code,
        # which re-reads certs/keys. Ideally we should share the instance.
        # But for now, we will create one to get the client.
        
        verifier_wrapper = SubscriptionVerifier()
        
        # Skip fetching if environment is Xcode (not supported by AppStoreServerAPIClient)
        # Skip fetching if environment is not PRODUCTION
        if verifier_wrapper.environment != Environment.PRODUCTION:
            logger.info(f"Skipping notification fetch in non-Production environment: {verifier_wrapper.environment}")
            return

        client = await verifier_wrapper.get_api_client()
        
        if not client:
            logger.warning("App Store API Client not available. Skipping fetch_missed_notifications.")
            return

        try:
            # Determine lookback window based on environment
            # Sandbox: 30 days
            # Production (and others): 180 days
            history_days = 180
            if verifier_wrapper.environment == Environment.SANDBOX:
                history_days = 30
            
            logger.info(f"Using {history_days}-day lookback window for environment: {verifier_wrapper.environment}")

            import time
            current_time = int(time.time() * 1000)
            start_date = current_time - (history_days * 24 * 60 * 60 * 1000)

            request = NotificationHistoryRequest(
                startDate=start_date,
                endDate=current_time
            )
            
            # We want to process notifications.
            # Paging is needed if there are more.
            # We will process the first page which should contain the most relevant recent ones if sorted (API doesn't specify sort order definitively but usually chronological).
            # The API returns 'notificationHistory' list.
            # Signature: get_notification_history(self, pagination_token, notification_history_request)
            
            response = client.get_notification_history(pagination_token=None, notification_history_request=request)
            
            if response and response.notificationHistory:
                logger.info(f"Found {len(response.notificationHistory)} notifications in history.")
                
                # Sort by fetched date just in case? Or trust the order.
                # We will just process them.
                # Limit to 100 as requested if there are more, though 
                # response.notificationHistory usually has a limit per page (e.g. 20).
                # To get 100 we might need multiple pages.
                
                count = 0
                max_count = 100
                
                # Check pagination
                while True:
                    if not response.notificationHistory:
                        break
                        
                    for item in response.notificationHistory:
                        if count >= max_count:
                             break
                        # item is NotificationHistoryResponseItem
                        # It contains 'signedPayload'
                        await self.process_signed_payload(item.signedPayload)
                        count += 1
                    
                    if count >= max_count or not response.paginationToken:
                        break
                        
                    # Fetch next page
                    # request.paginationToken = response.paginationToken # Not needed if passed as arg
                    response = client.get_notification_history(pagination_token=response.paginationToken, notification_history_request=request)
                    
                logger.info(f"Successfully processed {count} historical notifications.")
                
            else:
                logger.info("No notification history found.")
                
        except Exception as e:
            logger.error(f"Failed to fetch missed notifications: {e}")

# Global instance
_notification_handler = None

def get_notification_handler() -> AppStoreNotificationHandler:
    """Get or create global notification handler instance."""
    global _notification_handler
    if _notification_handler is None:
        _notification_handler = AppStoreNotificationHandler()
    return _notification_handler