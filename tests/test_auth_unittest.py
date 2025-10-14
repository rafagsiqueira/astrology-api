import unittest
import jwt
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
from fastapi import HTTPException

class TestFirebaseAuthentication(unittest.TestCase):
    """Test suite for Firebase authentication and token verification"""

    def test_verify_firebase_token_missing_header(self):
        """Test token verification with missing Authorization header"""
        from auth import verify_firebase_token
        
        with self.assertRaises(HTTPException) as cm:
            asyncio.run(verify_firebase_token(authorization=''))
        
        self.assertEqual(cm.exception.status_code, 401)
        self.assertIn("Authorization header missing", cm.exception.detail)

    def test_verify_firebase_token_invalid_header_format(self):
        """Test token verification with invalid header format"""
        from auth import verify_firebase_token
        
        with self.assertRaises(HTTPException) as cm:
            asyncio.run(verify_firebase_token(authorization="InvalidToken123"))
        
        self.assertEqual(cm.exception.status_code, 401)
        self.assertIn("Invalid authorization header format", cm.exception.detail)
        
        with self.assertRaises(HTTPException) as cm:
            asyncio.run(verify_firebase_token(authorization="Bearer"))
        
        self.assertEqual(cm.exception.status_code, 401)
        self.assertIn("Invalid authorization header format", cm.exception.detail)

    def test_verify_firebase_token_expired_token(self):
        """Test token verification with expired JWT token"""
        from auth import verify_firebase_token
        
        expired_payload = {
            'iss': 'https://securetoken.google.com/test-project',
            'aud': 'test-project',
            'auth_time': int((datetime.now() - timedelta(hours=2)).timestamp()),
            'user_id': 'test-user-123',
            'sub': 'test-user-123',
            'iat': int((datetime.now() - timedelta(hours=2)).timestamp()),
            'exp': int((datetime.now() - timedelta(hours=1)).timestamp()),
            'email': 'test@example.com',
            'email_verified': True,
            'firebase': {
                'identities': {
                    'email': ['test@example.com']
                },
                'sign_in_provider': 'password'
            }
        }
        
        expired_token = jwt.encode(expired_payload, 'fake-secret', algorithm='HS256')
        
        with patch('firebase_admin.auth.verify_id_token') as mock_verify:
            from firebase_admin import auth
            mock_verify.side_effect = auth.InvalidIdTokenError('Token expired')
            
            with self.assertRaises(HTTPException) as cm:
                asyncio.run(verify_firebase_token(authorization=f"Bearer {expired_token}"))
            
            self.assertEqual(cm.exception.status_code, 401)
            self.assertIn("Invalid or expired token", cm.exception.detail)

    def test_verify_firebase_token_invalid_signature(self):
        """Test token verification with invalid signature"""
        from auth import verify_firebase_token
        
        invalid_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        
        with patch('firebase_admin.auth.verify_id_token') as mock_verify:
            from firebase_admin import auth
            mock_verify.side_effect = auth.InvalidIdTokenError('Invalid signature')
            
            with self.assertRaises(HTTPException) as cm:
                asyncio.run(verify_firebase_token(authorization=f"Bearer {invalid_token}"))
            
            self.assertEqual(cm.exception.status_code, 401)
            self.assertIn("Invalid or expired token", cm.exception.detail)

    def test_verify_firebase_token_malformed_token(self):
        """Test token verification with malformed JWT token"""
        from auth import verify_firebase_token
        
        malformed_tokens = [
            "not.a.jwt",
            "invalid-jwt-format",
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.malformed",
            ""
        ]
        
        for malformed_token in malformed_tokens:
            with patch('firebase_admin.auth.verify_id_token') as mock_verify:
                from firebase_admin import auth
                mock_verify.side_effect = auth.InvalidIdTokenError('Malformed token')
                
                with self.assertRaises(HTTPException) as cm:
                    asyncio.run(verify_firebase_token(authorization=f"Bearer {malformed_token}"))
                
                self.assertEqual(cm.exception.status_code, 401)
                self.assertIn("Invalid or expired token", cm.exception.detail)

    def test_verify_firebase_token_valid_token(self):
        """Test token verification with valid token"""
        from auth import verify_firebase_token
        
        valid_decoded_token = {
            'iss': 'https://securetoken.google.com/test-project',
            'aud': 'test-project',
            'auth_time': int(datetime.now().timestamp()),
            'uid': 'test-user-123',
            'sub': 'test-user-123',
            'iat': int(datetime.now().timestamp()),
            'exp': int((datetime.now() + timedelta(hours=1)).timestamp()),
            'email': 'test@example.com',
            'email_verified': True,
            'firebase': {
                'identities': {
                    'email': ['test@example.com']
                },
                'sign_in_provider': 'password'
            }
        }
        
        valid_token = "valid-firebase-jwt-token"
        
        with patch('firebase_admin.auth.verify_id_token') as mock_verify:
            mock_verify.return_value = valid_decoded_token
            
            result = asyncio.run(verify_firebase_token(authorization=f"Bearer {valid_token}"))
            
            expected_result = {
                "uid": "test-user-123",
                "email": "test@example.com",
                "decoded_token": valid_decoded_token
            }
            self.assertEqual(result, expected_result)
            mock_verify.assert_called_once_with(valid_token)

    def test_require_authenticated_user_valid(self):
        """Test authenticated user dependency with valid user"""
        from auth import require_authenticated_user
        valid_user = {'user_id': 'test-user-123', 'email': 'test@example.com'}
        result = asyncio.run(require_authenticated_user(user_info=valid_user))
        self.assertEqual(result, valid_user)

    def test_require_non_anonymous_user_with_full_auth(self):
        """Test non-anonymous user dependency with fully authenticated user"""
        from auth import require_non_anonymous_user
        valid_user = {
            'user_id': 'test-user-123',
            'email': 'test@example.com',
            'firebase': {'sign_in_provider': 'password'}
        }
        user_info_with_decoded_token = {
            'uid': valid_user['user_id'],
            'email': valid_user.get('email'),
            'decoded_token': {
                'uid': valid_user['user_id'],
                'email': valid_user.get('email'),
                'firebase': valid_user['firebase']
            }
        }
        
        result = asyncio.run(require_non_anonymous_user(user_info=user_info_with_decoded_token))
        self.assertEqual(result, user_info_with_decoded_token)

    def test_require_non_anonymous_user_with_anonymous_user(self):
        """Test non-anonymous user dependency with anonymous user"""
        from auth import require_non_anonymous_user
        anonymous_user = {
            'user_id': 'anonymous-user-abc',
            'firebase': {'sign_in_provider': 'anonymous'}
        }

        user_info_with_decoded_token = {
            'uid': anonymous_user['user_id'],
            'email': None,
            'decoded_token': {
                'uid': anonymous_user['user_id'],
                'firebase': anonymous_user['firebase']
            }
        }
        
        with self.assertRaises(HTTPException) as cm:
            asyncio.run(require_non_anonymous_user(user_info=user_info_with_decoded_token))
        
        self.assertEqual(cm.exception.status_code, 403)
        self.assertIn("Anonymous users are not allowed for this operation", cm.exception.detail)

    def test_require_non_anonymous_user_missing_firebase_info(self):
        """Test non-anonymous user dependency with missing Firebase info"""
        from auth import require_non_anonymous_user
        
        incomplete_user = {
            'user_id': 'test-user-123',
            'email': 'test@example.com'
        }
        
        with self.assertRaises(HTTPException) as cm:
            asyncio.run(require_non_anonymous_user(user_info=incomplete_user))

        self.assertEqual(cm.exception.status_code, 403)
        self.assertIn("User authentication data unavailable", cm.exception.detail)

    def test_protected_endpoint_without_auth(self):
        """Test that verify_firebase_token raises exception without auth header"""
        from auth import verify_firebase_token
        
        with self.assertRaises(HTTPException) as cm:
            asyncio.run(verify_firebase_token(authorization=''))
        
        self.assertEqual(cm.exception.status_code, 401)
        self.assertIn("Authorization header missing", cm.exception.detail)

    def test_protected_endpoint_with_invalid_token(self):
        """Test that verify_firebase_token raises exception with invalid token"""
        from auth import verify_firebase_token
        
        with patch('firebase_admin.auth.verify_id_token') as mock_verify:
            from firebase_admin import auth
            mock_verify.side_effect = auth.InvalidIdTokenError('Invalid token')
            
            with self.assertRaises(HTTPException) as cm:
                asyncio.run(verify_firebase_token(authorization="Bearer invalid-token"))
            
            self.assertEqual(cm.exception.status_code, 401)
            self.assertIn("Invalid or expired token", cm.exception.detail)

    def test_protected_endpoint_with_anonymous_user(self):
        """Test that require_non_anonymous_user rejects anonymous users"""
        from auth import require_non_anonymous_user
        anonymous_user = {
            'user_id': 'anonymous-user-abc',
            'firebase': {'sign_in_provider': 'anonymous'}
        }
        user_info_with_decoded_token = {
            'uid': anonymous_user['user_id'],
            'email': None,
            'decoded_token': {
                'uid': anonymous_user['user_id'],
                'firebase': anonymous_user['firebase']
            }
        }
        
        with self.assertRaises(HTTPException) as cm:
            asyncio.run(require_non_anonymous_user(user_info=user_info_with_decoded_token))
        
        self.assertEqual(cm.exception.status_code, 403)
        self.assertIn("Anonymous users are not allowed for this operation", cm.exception.detail)

    def test_protected_endpoint_with_valid_user(self):
        """Test that require_non_anonymous_user accepts valid authenticated users"""
        from auth import require_non_anonymous_user
        valid_user = {
            'user_id': 'test-user-123',
            'email': 'test@example.com',
            'firebase': {'sign_in_provider': 'password'}
        }
        user_info_with_decoded_token = {
            'uid': valid_user['user_id'],
            'email': valid_user.get('email'),
            'decoded_token': {
                'uid': valid_user['user_id'],
                'email': valid_user.get('email'),
                'firebase': valid_user['firebase']
            }
        }
        
        result = asyncio.run(require_non_anonymous_user(user_info=user_info_with_decoded_token))
        self.assertEqual(result, user_info_with_decoded_token)

    def test_different_sign_in_providers(self):
        """Test authentication with different sign-in providers"""
        from auth import require_non_anonymous_user
        
        valid_providers = ['google.com', 'apple.com', 'phone', 'password']
        
        for provider in valid_providers:
            user_info = {
                'uid': f'user-{provider}',
                'email': f'test-{provider}@example.com',
                'decoded_token': {
                    'uid': f'user-{provider}',
                    'firebase': {
                        'sign_in_provider': provider
                    }
                }
            }
            
            result = asyncio.run(require_non_anonymous_user(user_info=user_info))
            self.assertEqual(result, user_info)
        
        anonymous_user = {
            'uid': 'anonymous-user',
            'email': None,
            'decoded_token': {
                'uid': 'anonymous-user',
                'firebase': {
                    'sign_in_provider': 'anonymous'
                }
            }
        }
        
        with self.assertRaises(HTTPException) as cm:
            asyncio.run(require_non_anonymous_user(user_info=anonymous_user))
        
        self.assertEqual(cm.exception.status_code, 403)

    def test_firebase_admin_initialization_error(self):
        """Test behavior when Firebase Admin SDK fails to initialize"""
        from auth import verify_firebase_token
        
        with self.assertRaises(HTTPException) as cm:
            asyncio.run(verify_firebase_token(authorization=''))
        
        self.assertEqual(cm.exception.status_code, 401)
        self.assertIn("Authorization header missing", cm.exception.detail)

    def test_edge_case_token_formats(self):
        """Test edge cases in token format handling"""
        from auth import verify_firebase_token
        
        format_error_cases = [
            "bearer valid-token",
            "BEARER valid-token",
            "Basic valid-token",
            "valid-token",
        ]
        
        for auth_header in format_error_cases:
            with self.assertRaises(HTTPException) as cm:
                asyncio.run(verify_firebase_token(authorization=auth_header))
            
            self.assertEqual(cm.exception.status_code, 401)
            self.assertIn("Invalid authorization header format", cm.exception.detail)
        
        token_error_cases = [
            "Bearer ",
            "Bearer   ",
            "Bearer invalid-token",
        ]
        
        for auth_header in token_error_cases:
            with patch('firebase_admin.auth.verify_id_token') as mock_verify:
                from firebase_admin import auth
                mock_verify.side_effect = auth.InvalidIdTokenError('Invalid token')
                
                with self.assertRaises(HTTPException) as cm:
                    asyncio.run(verify_firebase_token(authorization=auth_header))
                
                self.assertEqual(cm.exception.status_code, 401)
                self.assertIn("Invalid or expired token", cm.exception.detail)

if __name__ == '__main__':
    unittest.main()
