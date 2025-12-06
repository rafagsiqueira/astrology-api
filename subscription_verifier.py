import os
from typing import Optional
from appstoreserverlibrary.api_client import AppStoreServerAPIClient
from appstoreserverlibrary.models.Environment import Environment
from appstoreserverlibrary.models.JWSTransactionDecodedPayload import JWSTransactionDecodedPayload
from appstoreserverlibrary.signed_data_verifier import SignedDataVerifier
from config import get_logger
import jwt

logger = get_logger(__name__)

class SubscriptionVerifier:
    """Verifies App Store receipts and subscriptions."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SubscriptionVerifier, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
            
        self.bundle_id = os.getenv("IOS_BUNDLE_ID", "com.rafasiqueira.avra")
        self.issuer_id = os.getenv("APP_STORE_ISSUER_ID")
        self.key_id = os.getenv("APP_STORE_KEY_ID")
        self.private_key = os.getenv("APP_STORE_PRIVATE_KEY")
        self.app_id = os.getenv("APP_ID")
        self.environment = get_environment()
        
        self._client: Optional[AppStoreServerAPIClient] = None
        self._initialize_client()
        self._initialized = True

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

            # Load Apple Root Certificates
            root_certificates = []
            
            # Directories to check for certificates
            cert_dir = os.path.join(os.path.dirname(__file__), "assets", "root_certs")
            
            if os.path.exists(cert_dir):
                for filename in os.listdir(cert_dir):
                    if filename.endswith(".cer"):
                        filepath = os.path.join(cert_dir, filename)
                        try:
                            with open(filepath, "rb") as f:
                                cert_content = f.read()
                                root_certificates.append(cert_content)
                                logger.info(f"Loaded root certificate: {filename}")
                        except Exception as e:
                            logger.warning(f"Failed to load certificate {filename}: {e}")

            if not root_certificates:
                logger.warning("No Apple Root Certificates found.")
                return

            # Assert that we have the 3 expected root certificates
            if len(root_certificates) != 3:
                 logger.error(f"Expected 3 root certificates, found {len(root_certificates)}")
            assert len(root_certificates) == 3, f"Expected 3 root certificates, but found {len(root_certificates)}"

            logger.info(f"Lenght of chain: {len(root_certificates)}")

            self._verifier = SignedDataVerifier(
                root_certificates=root_certificates,
                bundle_id=self.bundle_id,
                environment=self.environment,
                app_apple_id=self.app_id,
                enable_online_checks=True
            )
        except ValueError as e:
            logger.warn(f"Failed to initialize API client. Are you running on a valid environment?")
        except Exception as e:
            logger.error(f"Failed to initialize SubscriptionVerifier: {e}")

    async def get_api_client(self) -> Optional[AppStoreServerAPIClient]:
        """Get the initialized AppStoreServerAPIClient instance."""
        if not self._client:
            # Try to re-initialize if missing (lazy loading attempt)
             self._initialize_client()
        return self._client

    def get_verifier(self) -> Optional[SignedDataVerifier]:
        """Get the initialized SignedDataVerifier instance."""
        return self._verifier

    async def verify_transaction(self, request: dict) -> JWSTransactionDecodedPayload:
        """
        Verify a transaction ID with Apple and return the transaction info.
        
        Args:
            transaction_id: The original transaction ID or transaction ID from the receipt.
            
        Returns:
            Dictionary with transaction details if valid, None otherwise.
        """
        transaction_id = request.get("transactionId")
        signed_data = request.get("verificationData")

        logger.info(f"Verifying transaction {transaction_id} with Bundle ID: {self.bundle_id}, Environment: {self.environment}")
        
        if self.environment == Environment.XCODE:
            logger.warning("Bypassing verification for Xcode environment.")
            if not signed_data:
                 logger.error("No signed data provided for Xcode verification bypass")
                 return None
            try:
                # Decode JWS without verification
                decoded_data = jwt.decode(signed_data, options={"verify_signature": False})
                logger.info(f"Decoded payload in Xcode mode: {decoded_data}")
                
                 # Create JWSTransactionDecodedPayload from decoded data
                 # We filter keys to ensure we don't pass unexpected arguments if the payload has extras
                valid_keys = JWSTransactionDecodedPayload.__init__.__code__.co_varnames
                filtered_data = {k: v for k, v in decoded_data.items() if k in valid_keys}
                
                return JWSTransactionDecodedPayload(**filtered_data)
            except Exception as e:
                logger.error(f"Failed to decode JWS in Xcode mode: {e}")
                import traceback
                traceback.print_exc()
                return None

        if not self._verifier:
            raise("SubscriptionVerifier not fully initialized")

        try:
            # Verify and decode the signed transaction info
            verified_transaction = self._verifier.verify_and_decode_signed_transaction(signed_data)
            
            logger.debug(f"Verified transaction {verified_transaction}")
            return verified_transaction
            
        except Exception as e:
            logger.error(f"Failed to verify transaction {transaction_id}: {e} (Type: {type(e).__name__})", exc_info=True)
            logger.error(e)
            return None

def get_environment():
    env = os.getenv("APP_ENV")
    if env == "sandbox":
        return Environment.SANDBOX
    elif env == "xcode":
        return Environment.XCODE
    elif env == "local":
        return Environment.LOCAL
    else:
        return Environment.PRODUCTION
