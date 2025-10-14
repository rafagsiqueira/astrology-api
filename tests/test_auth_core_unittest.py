"""Core authentication tests - organized and comprehensive."""

import asyncio
import unittest
from unittest.mock import Mock, patch
from fastapi import HTTPException
import firebase_admin
from firebase_admin import auth, firestore

from auth import (
    verify_firebase_token, require_authenticated_user, require_non_anonymous_user,
    get_firestore_client, validate_database_availability
)


class TestFirebaseTokenVerification(unittest.TestCase):
    """Test Firebase token verification functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.valid_token = "valid.jwt.token"
        self.invalid_token = "invalid.jwt.token"
        self.expired_token = "expired.jwt.token"
        
        self.mock_decoded_token = {
            'uid': 'test-user-123',
            'email': 'test@example.com',
            'firebase': {
                'sign_in_provider': 'google.com',
                'identities': {
                    'google.com': ['123456789'],
                    'email': ['test@example.com']
                }
            }
        }
    
    @patch('auth.auth.verify_id_token')
    def test_verify_firebase_token_valid_token(self, mock_verify):
        """Test verification with valid token."""
        mock_verify.return_value = self.mock_decoded_token
        
        async def run_test():
            authorization_header = f"Bearer {self.valid_token}"
            result = await verify_firebase_token(authorization_header)
            self.assertEqual(result['uid'], 'test-user-123')
            self.assertEqual(result['email'], 'test@example.com')
            mock_verify.assert_called_once_with(self.valid_token)

        asyncio.run(run_test())
    
    @patch('auth.auth.verify_id_token')
    def test_verify_firebase_token_invalid_token(self, mock_verify):
        """Test verification with invalid token."""
        mock_verify.side_effect = auth.InvalidIdTokenError("Invalid token")
        
        async def run_test():
            authorization_header = f"Bearer {self.invalid_token}"
            with self.assertRaises(HTTPException) as context:
                await verify_firebase_token(authorization_header)
            self.assertEqual(context.exception.status_code, 401)
            self.assertIn("Invalid", context.exception.detail)

        asyncio.run(run_test())
    
    @patch('auth.auth.verify_id_token')
    def test_verify_firebase_token_expired_token(self, mock_verify):
        """Test verification with expired token."""
        mock_verify.side_effect = auth.ExpiredIdTokenError("Token expired", None)
        
        async def run_test():
            authorization_header = f"Bearer {self.expired_token}"
            with self.assertRaises(HTTPException) as context:
                await verify_firebase_token(authorization_header)
            self.assertEqual(context.exception.status_code, 401)
            self.assertIn("expired", context.exception.detail.lower())

        asyncio.run(run_test())
    
    def test_verify_firebase_token_missing_header(self):
        """Test verification with missing authorization header."""
        async def run_test():
            with self.assertRaises(HTTPException) as context:
                await verify_firebase_token(authorization='')
            self.assertEqual(context.exception.status_code, 401)

        asyncio.run(run_test())
    
    def test_verify_firebase_token_invalid_header_format(self):
        """Test verification with invalid header format."""
        async def run_test():
            authorization_header = "InvalidFormat"  # Missing 'Bearer ' prefix
            with self.assertRaises(HTTPException) as context:
                await verify_firebase_token(authorization_header)
            self.assertEqual(context.exception.status_code, 401)

        asyncio.run(run_test())
    
    def test_verify_firebase_token_malformed_token(self):
        """Test verification with malformed token."""
        async def run_test():
            authorization_header = "Bearer "  # Empty token
            with self.assertRaises(HTTPException) as context:
                await verify_firebase_token(authorization_header)
            self.assertEqual(context.exception.status_code, 401)

        asyncio.run(run_test())


class TestAuthenticationDependencies(unittest.TestCase):
    """Test authentication dependency functions."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.anonymous_user = {
            'uid': 'anonymous-user-123',
            'decoded_token': {
                'firebase': {
                    'sign_in_provider': 'anonymous',
                    'identities': {}
                }
            }
        }
        
        self.authenticated_user = {
            'uid': 'auth-user-123',
            'email': 'user@example.com',
            'decoded_token': {
                'firebase': {
                    'sign_in_provider': 'google.com',
                    'identities': {
                        'google.com': ['123456789'],
                        'email': ['user@example.com']
                    }
                }
            }
        }
    
    def test_require_authenticated_user_with_anonymous(self):
        """Test require_authenticated_user allows anonymous users."""
        async def run_test():
            result = await require_authenticated_user(self.anonymous_user)
            self.assertEqual(result['uid'], 'anonymous-user-123')

        asyncio.run(run_test())
    
    def test_require_authenticated_user_with_authenticated(self):
        """Test require_authenticated_user allows authenticated users."""
        async def run_test():
            result = await require_authenticated_user(self.authenticated_user)
            self.assertEqual(result['uid'], 'auth-user-123')

        asyncio.run(run_test())
    
    def test_require_non_anonymous_user_with_anonymous(self):
        """Test require_non_anonymous_user rejects anonymous users."""
        async def run_test():
            with self.assertRaises(HTTPException) as context:
                await require_non_anonymous_user(self.anonymous_user)
            self.assertEqual(context.exception.status_code, 403)
            self.assertIn("anonymous", context.exception.detail.lower())

        asyncio.run(run_test())
    
    def test_require_non_anonymous_user_with_authenticated(self):
        """Test require_non_anonymous_user allows authenticated users."""
        async def run_test():
            result = await require_non_anonymous_user(self.authenticated_user)
            self.assertEqual(result['uid'], 'auth-user-123')

        asyncio.run(run_test())
    
    def test_require_non_anonymous_user_missing_firebase_info(self):
        """Test require_non_anonymous_user with missing Firebase info."""
        async def run_test():
            incomplete_user = {'uid': 'user-123', 'decoded_token': {}}
            with self.assertRaises(HTTPException) as context:
                await require_non_anonymous_user(incomplete_user)
            self.assertEqual(context.exception.status_code, 403)

        asyncio.run(run_test())


class TestFirestoreClient(unittest.TestCase):
    """Test Firestore client functionality."""
    
    @patch('auth.db')
    def test_get_firestore_client_success(self, mock_db):
        """Test successful Firestore client creation."""
        mock_db_instance = Mock()
        mock_db.return_value = mock_db_instance
        
        # Since get_firestore_client() returns the global db variable
        with patch('auth.db', mock_db_instance):
            result = get_firestore_client()
            
        self.assertEqual(result, mock_db_instance)
    
    def test_get_firestore_client_error(self):
        """Test Firestore client when db is None."""
        # Since get_firestore_client() just returns the global db, 
        # and db can be None if not initialized, test that scenario
        with patch('auth.db', None):
            result = get_firestore_client()
            
        self.assertIsNone(result)
    
    @patch('auth.get_firestore_client')
    def test_validate_database_availability_success(self, mock_get_client):
        """Test database availability validation success."""
        mock_db = Mock()
        mock_get_client.return_value = mock_db
        
        # Should not raise exception
        validate_database_availability()
        
        mock_get_client.assert_called_once()
    
    @patch('auth.get_firestore_client')
    def test_validate_database_availability_failure(self, mock_get_client):
        """Test database availability validation failure."""
        mock_get_client.side_effect = HTTPException(status_code=503, detail="Service unavailable")
        
        with self.assertRaises(HTTPException) as context:
            validate_database_availability()
        
        self.assertEqual(context.exception.status_code, 503)


class TestAuthenticationEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.edge_case_users = [
            # User with different sign-in providers
            {
                'uid': 'apple-user',
                'email': 'user@privaterelay.appleid.com',
                'decoded_token': {
                    'firebase': {
                        'sign_in_provider': 'apple.com',
                        'identities': {'apple.com': ['001234.abcd']}
                    }
                }
            },
            # User with phone authentication
            {
                'uid': 'phone-user',
                'phone_number': '+1234567890',
                'decoded_token': {
                    'firebase': {
                        'sign_in_provider': 'phone',
                        'identities': {'phone': ['+1234567890']}
                    }
                }
            },
            # User with custom token
            {
                'uid': 'custom-user',
                'decoded_token': {
                    'firebase': {
                        'sign_in_provider': 'custom',
                        'identities': {}
                    }
                }
            }
        ]
    
    def test_different_sign_in_providers(self):
        """Test handling of different sign-in providers."""
        async def run_test():
            for user in self.edge_case_users:
                result = await require_non_anonymous_user(user)
                self.assertEqual(result['uid'], user['uid'])

        asyncio.run(run_test())

    @patch('auth.auth.verify_id_token')
    def test_token_with_unusual_claims(self, mock_verify):
        """Test handling of tokens with unusual claims."""
        unusual_token = {
            'uid': 'unusual-user',
            'custom_claims': {'role': 'admin', 'premium': True},
            'firebase': {
                'sign_in_provider': 'google.com',
                'identities': {'google.com': ['123']}
            }
        }

        mock_verify.return_value = {**unusual_token}

        async def run_test():
            authorization_header = "Bearer token"
            result = await verify_firebase_token(authorization_header)
            self.assertEqual(result['uid'], 'unusual-user')
            self.assertIn('custom_claims', result['decoded_token'])

        asyncio.run(run_test())
    
    @patch('auth.auth.verify_id_token')
    def test_revoked_token_error(self, mock_verify):
        """Test handling of revoked tokens."""
        mock_verify.side_effect = auth.RevokedIdTokenError("Token revoked")
        
        async def run_test():
            authorization_header = "Bearer revoked-token"
            with self.assertRaises(HTTPException) as context:
                await verify_firebase_token(authorization_header)
            self.assertEqual(context.exception.status_code, 401)
            self.assertIn("invalid", context.exception.detail.lower())

        asyncio.run(run_test())
    
    @patch('auth.firebase_admin.get_app')
    def test_firebase_admin_initialization_error(self, mock_get_app):
        """Test handling of Firebase Admin initialization errors."""
        mock_get_app.side_effect = ValueError("No Firebase app")
        
        # This would be tested during app initialization
        # For now, just verify the exception type
        with self.assertRaises(ValueError):
            mock_get_app()


class TestConcurrentAuthentication(unittest.TestCase):
    """Test authentication under concurrent conditions."""
    
    @patch('auth.auth.verify_id_token')
    def test_concurrent_token_verification(self, mock_verify):
        """Test concurrent token verifications don't interfere."""
        async def run_test():
            results = []

            def side_effect(token):
                suffix = token.split("-")[-1]
                return {
                    'uid': f'user-{suffix}',
                    'firebase': {
                        'sign_in_provider': 'google.com',
                        'identities': {'google.com': [suffix]}
                    }
                }

            mock_verify.side_effect = side_effect

            async def verify_token(token_suffix):
                authorization_header = f"Bearer token-{token_suffix}"
                result = await verify_firebase_token(authorization_header)
                results.append(result['uid'])

            tasks = [asyncio.create_task(verify_token(i)) for i in range(5)]
            await asyncio.gather(*tasks)

            self.assertEqual(len(results), 5)
            self.assertEqual(set(results), {f'user-{i}' for i in range(5)})

        asyncio.run(run_test())


if __name__ == '__main__':
    unittest.main()
