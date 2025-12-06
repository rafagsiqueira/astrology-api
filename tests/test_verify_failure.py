import unittest
from unittest.mock import Mock, patch
import asyncio
import sys
import os

# Add backend to path so we can import routes
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestVerificationFailure(unittest.TestCase):
    def test_verify_subscription_failure_returns_200(self):
        """
        Test that verify_subscription returns a 200 OK with status='verification_failed'
        when the verifier returns None (fails to verify), instead of raising a 400 error.
        """
        from routes import verify_subscription
        
        # Mock payload and user
        request_payload = {"transactionId": "test_tx_123", "verificationData": "some_data"}
        user = {"uid": "test_user"}
        
        # Patch SubscriptionVerifier
        with patch('routes.SubscriptionVerifier') as MockVerifierClass:
            mock_verifier_instance = MockVerifierClass.return_value
            # configure verify_transaction to return None (failure)
            mock_verifier_instance.verify_transaction = Mock(return_value=None)
            # Make it an async mock if needed, but the route awaits it, so it should be Awaitable or AsyncMock
            # Looking at routes.py: validated_transaction = await verifier.verify_transaction(request)
            # So verify_transaction must be awaitable.
            
            async def async_return_none(*args, **kwargs):
                return None
            
            mock_verifier_instance.verify_transaction = async_return_none

            # Call the endpoint
            result = asyncio.run(verify_subscription(request_payload, user))
            
            # Assertions
            self.assertEqual(result, {"status": "verification_failed", "transaction": None})
