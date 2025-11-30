import os
from typing import Optional
from appstoreserverlibrary.api_client import AppStoreServerAPIClient
from appstoreserverlibrary.models.Environment import Environment
from appstoreserverlibrary.signed_data_verifier import SignedDataVerifier
from config import get_logger

logger = get_logger(__name__)

class SubscriptionVerifier:
    """Verifies App Store receipts and subscriptions."""

    def __init__(self):
        self.bundle_id = os.getenv("IOS_BUNDLE_ID", "com.rafasiqueira.avra")
        self.issuer_id = os.getenv("APP_STORE_ISSUER_ID")
        self.key_id = os.getenv("APP_STORE_KEY_ID")
        self.private_key = os.getenv("APP_STORE_PRIVATE_KEY")
        self.environment = Environment.SANDBOX if os.getenv("APP_ENV") != "production" else Environment.PRODUCTION
        
        self._client: Optional[AppStoreServerAPIClient] = None
        self._initialize_client()

    def _initialize_client(self):
        """Initialize the AppStoreServerAPIClient and SignedDataVerifier."""
        if not all([self.issuer_id, self.key_id, self.private_key, self.bundle_id]):
            logger.warning("App Store credentials missing. Receipt verification will fail.")
            return

        try:
            with open(self.private_key, "rb") as f:
                private_key_content = f.read()
            
            self._client = AppStoreServerAPIClient(
                signing_key=private_key_content,
                key_id=self.key_id,
                issuer_id=self.issuer_id,
                bundle_id=self.bundle_id,
                environment=self.environment
            )

            # Load Apple Root Certificate
            cert_path = os.path.join(os.path.dirname(__file__), "assets", "AppleIncRootCertificate.pem")
            if not os.path.exists(cert_path):
                logger.warning(f"Apple Root Certificate not found at {cert_path}")
                return

            with open(cert_path, "rb") as f:
                root_certificates = [f.read()]

            self._verifier = SignedDataVerifier(
                root_certificates=root_certificates,
                bundle_id=self.bundle_id,
                environment=self.environment,
                app_apple_id=None, # Optional
                enable_online_checks=True
            )
            
        except Exception as e:
            logger.error(f"Failed to initialize SubscriptionVerifier: {e}")

    async def verify_transaction(self, transaction_id: str) -> Optional[dict]:
        """
        Verify a transaction ID with Apple and return the transaction info.
        
        Args:
            transaction_id: The original transaction ID or transaction ID from the receipt.
            
        Returns:
            Dictionary with transaction details if valid, None otherwise.
        """
        if not self._client or not self._verifier:
            logger.error("SubscriptionVerifier not fully initialized")
            return None

        logger.info(f"Verifying transaction {transaction_id} with Bundle ID: {self.bundle_id}, Environment: {self.environment}")

        try:
            # Get transaction info from Apple
            response = self._client.get_transaction_info(transaction_id)
            
            if not response or not response.signedTransactionInfo:
                logger.error("No signed transaction info received from Apple")
                return None
                
            # Verify and decode the signed transaction info
            verified_transaction = self._verifier.verify_and_decode_signed_transaction(response.signedTransactionInfo)
            
            # Convert AppTransaction object to dict for easier usage
            # The library returns a pydantic model or similar object
            # We can use vars() or .__dict__ or manual mapping
            
            # Assuming verified_transaction is an AppTransaction object
            # We'll return a dict representation
            
            # Note: The library might return a specific object type. 
            # Let's assume it has attributes matching the JSON fields.
            
            # Helper to convert to dict (simplified)
            return {
                "transactionId": verified_transaction.transactionId,
                "originalTransactionId": verified_transaction.originalTransactionId,
                "productId": verified_transaction.productId,
                "purchaseDate": verified_transaction.purchaseDate,
                "expiresDate": verified_transaction.expiresDate,
                "revocationDate": verified_transaction.revocationDate,
                "environment": verified_transaction.environment,
                # Add other fields as needed
            }
            
        except Exception as e:
            logger.error(f"Failed to verify transaction {transaction_id}: {e} (Type: {type(e).__name__})", exc_info=True)
            logger.error(e)
            return None
