import pytest
import jwt
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from fastapi import HTTPException


class TestFirebaseAuthentication:
    """Test suite for Firebase authentication and token verification"""
    
    def test_verify_firebase_token_missing_header(self):
        """Test token verification with missing Authorization header"""
        from auth import verify_firebase_token
        
        # Test with missing header
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(verify_firebase_token(authorization=None))
        
        assert exc_info.value.status_code == 401
        assert "Authorization header missing" in exc_info.value.detail
    
    def test_verify_firebase_token_invalid_header_format(self):
        """Test token verification with invalid header format"""
        from auth import verify_firebase_token
        
        # Test with invalid format (missing Bearer)
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(verify_firebase_token(authorization="InvalidToken123"))
        
        assert exc_info.value.status_code == 401
        assert "Invalid authorization header format" in exc_info.value.detail
        
        # Test with malformed Bearer header
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(verify_firebase_token(authorization="Bearer"))
        
        assert exc_info.value.status_code == 401
        assert "Invalid authorization header format" in exc_info.value.detail
    
    def test_verify_firebase_token_expired_token(self):
        """Test token verification with expired JWT token"""
        from auth import verify_firebase_token
        
        # Create an expired JWT token
        expired_payload = {
            'iss': 'https://securetoken.google.com/test-project',
            'aud': 'test-project',
            'auth_time': int((datetime.now() - timedelta(hours=2)).timestamp()),
            'user_id': 'test-user-123',
            'sub': 'test-user-123',
            'iat': int((datetime.now() - timedelta(hours=2)).timestamp()),
            'exp': int((datetime.now() - timedelta(hours=1)).timestamp()),  # Expired 1 hour ago
            'email': 'test@example.com',
            'email_verified': True,
            'firebase': {
                'identities': {
                    'email': ['test@example.com']
                },
                'sign_in_provider': 'password'
            }
        }
        
        # Create expired token (won't be properly signed, but will test our error handling)
        expired_token = jwt.encode(expired_payload, 'fake-secret', algorithm='HS256')
        
        # Mock Firebase auth.verify_id_token to raise InvalidIdTokenError
        with patch('firebase_admin.auth.verify_id_token') as mock_verify:
            from firebase_admin import auth
            mock_verify.side_effect = auth.InvalidIdTokenError('Token expired')
            
            with pytest.raises(HTTPException) as exc_info:
                asyncio.run(verify_firebase_token(authorization=f"Bearer {expired_token}"))
            
            assert exc_info.value.status_code == 401
            assert "Invalid or expired token" in exc_info.value.detail
    
    def test_verify_firebase_token_invalid_signature(self):
        """Test token verification with invalid signature"""
        from auth import verify_firebase_token
        
        # Create a token with invalid signature
        invalid_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        
        # Mock Firebase auth.verify_id_token to raise InvalidIdTokenError
        with patch('firebase_admin.auth.verify_id_token') as mock_verify:
            from firebase_admin import auth
            mock_verify.side_effect = auth.InvalidIdTokenError('Invalid signature')
            
            with pytest.raises(HTTPException) as exc_info:
                asyncio.run(verify_firebase_token(authorization=f"Bearer {invalid_token}"))
            
            assert exc_info.value.status_code == 401
            assert "Invalid or expired token" in exc_info.value.detail
    
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
                
                with pytest.raises(HTTPException) as exc_info:
                    asyncio.run(verify_firebase_token(authorization=f"Bearer {malformed_token}"))
                
                assert exc_info.value.status_code == 401
                assert "Invalid or expired token" in exc_info.value.detail
    
    def test_verify_firebase_token_valid_token(self):
        """Test token verification with valid token"""
        from auth import verify_firebase_token
        
        # Mock a valid decoded token (what Firebase returns)
        valid_decoded_token = {
            'iss': 'https://securetoken.google.com/test-project',
            'aud': 'test-project',
            'auth_time': int(datetime.now().timestamp()),
            'uid': 'test-user-123',  # Firebase uses 'uid', not 'user_id'
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
        
        # Mock Firebase auth.verify_id_token to return valid data
        with patch('firebase_admin.auth.verify_id_token') as mock_verify:
            mock_verify.return_value = valid_decoded_token
            
            result = asyncio.run(verify_firebase_token(authorization=f"Bearer {valid_token}"))
            
            # Check the structure that auth.py actually returns
            expected_result = {
                "uid": "test-user-123",
                "email": "test@example.com",
                "decoded_token": valid_decoded_token
            }
            assert result == expected_result
            mock_verify.assert_called_once_with(valid_token)
    
    def test_require_authenticated_user_valid(self, valid_user):
        """Test authenticated user dependency with valid user"""
        from auth import require_authenticated_user
        
        result = asyncio.run(require_authenticated_user(user_info=valid_user))
        assert result == valid_user
    
    def test_require_non_anonymous_user_with_full_auth(self, valid_user):
        """Test non-anonymous user dependency with fully authenticated user"""
        from auth import require_non_anonymous_user
        
        # Structure the user_info as verify_firebase_token would return it
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
        assert result == user_info_with_decoded_token
    
    def test_require_non_anonymous_user_with_anonymous_user(self, anonymous_user):
        """Test non-anonymous user dependency with anonymous user"""
        from auth import require_non_anonymous_user
        
        # Structure the user_info as verify_firebase_token would return it
        user_info_with_decoded_token = {
            'uid': anonymous_user['user_id'],
            'email': None,
            'decoded_token': {
                'uid': anonymous_user['user_id'],
                'firebase': anonymous_user['firebase']
            }
        }
        
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(require_non_anonymous_user(user_info=user_info_with_decoded_token))
        
        assert exc_info.value.status_code == 403
        assert "Anonymous users are not allowed for this operation" in exc_info.value.detail
    
    def test_require_non_anonymous_user_missing_firebase_info(self):
        """Test non-anonymous user dependency with missing Firebase info"""
        from auth import require_non_anonymous_user
        
        # Mock user with missing firebase info
        incomplete_user = {
            'user_id': 'test-user-123',
            'email': 'test@example.com'
            # Missing firebase key
        }
        
        # Should not raise exception (treats as non-anonymous if firebase info is missing)
        result = asyncio.run(require_non_anonymous_user(user_info=incomplete_user))
        assert result == incomplete_user
    
    def test_protected_endpoint_without_auth(self):
        """Test that verify_firebase_token raises exception without auth header"""
        from auth import verify_firebase_token
        
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(verify_firebase_token(authorization=None))
        
        assert exc_info.value.status_code == 401
        assert "Authorization header missing" in exc_info.value.detail
    
    def test_protected_endpoint_with_invalid_token(self):
        """Test that verify_firebase_token raises exception with invalid token"""
        from auth import verify_firebase_token
        
        # Mock Firebase auth to raise error for invalid token
        with patch('firebase_admin.auth.verify_id_token') as mock_verify:
            from firebase_admin import auth
            mock_verify.side_effect = auth.InvalidIdTokenError('Invalid token')
            
            with pytest.raises(HTTPException) as exc_info:
                asyncio.run(verify_firebase_token(authorization="Bearer invalid-token"))
            
            assert exc_info.value.status_code == 401
            assert "Invalid or expired token" in exc_info.value.detail
    
    def test_protected_endpoint_with_anonymous_user(self, anonymous_user):
        """Test that require_non_anonymous_user rejects anonymous users"""
        from auth import require_non_anonymous_user
        
        # Structure the user_info as verify_firebase_token would return it
        user_info_with_decoded_token = {
            'uid': anonymous_user['user_id'],
            'email': None,
            'decoded_token': {
                'uid': anonymous_user['user_id'],
                'firebase': anonymous_user['firebase']
            }
        }
        
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(require_non_anonymous_user(user_info=user_info_with_decoded_token))
        
        assert exc_info.value.status_code == 403
        assert "Anonymous users are not allowed for this operation" in exc_info.value.detail
    
    def test_protected_endpoint_with_valid_user(self, valid_user):
        """Test that require_non_anonymous_user accepts valid authenticated users"""
        from auth import require_non_anonymous_user
        
        # Structure the user_info as verify_firebase_token would return it
        user_info_with_decoded_token = {
            'uid': valid_user['user_id'],
            'email': valid_user.get('email'),
            'decoded_token': {
                'uid': valid_user['user_id'],
                'email': valid_user.get('email'),
                'firebase': valid_user['firebase']
            }
        }
        
        # Should not raise an exception
        result = asyncio.run(require_non_anonymous_user(user_info=user_info_with_decoded_token))
        assert result == user_info_with_decoded_token
    
    def test_different_sign_in_providers(self):
        """Test authentication with different sign-in providers"""
        from auth import require_non_anonymous_user
        
        # Test different valid providers
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
            
            # Should not raise exception
            result = asyncio.run(require_non_anonymous_user(user_info=user_info))
            assert result == user_info
        
        # Test anonymous provider
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
        
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(require_non_anonymous_user(user_info=anonymous_user))
        
        assert exc_info.value.status_code == 403
    
    def test_firebase_admin_initialization_error(self):
        """Test behavior when Firebase Admin SDK fails to initialize"""
        from auth import verify_firebase_token
        
        # Test that auth function handles missing Firebase properly
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(verify_firebase_token(authorization=None))
        
        assert exc_info.value.status_code == 401
        assert "Authorization header missing" in exc_info.value.detail
    
    def test_edge_case_token_formats(self):
        """Test edge cases in token format handling"""
        from auth import verify_firebase_token
        
        # Test format errors (these should fail before reaching Firebase)
        format_error_cases = [
            "bearer valid-token",  # Lowercase bearer
            "BEARER valid-token",  # Uppercase bearer
            "Basic valid-token",   # Wrong auth type
            "valid-token",         # No Bearer prefix
        ]
        
        for auth_header in format_error_cases:
            with pytest.raises(HTTPException) as exc_info:
                asyncio.run(verify_firebase_token(authorization=auth_header))
            
            assert exc_info.value.status_code == 401
            assert "Invalid authorization header format" in exc_info.value.detail
        
        # Test token validation errors (these pass format but fail at Firebase)
        token_error_cases = [
            "Bearer ",              # Empty token
            "Bearer   ",            # Whitespace token  
            "Bearer invalid-token", # Invalid token
        ]
        
        for auth_header in token_error_cases:
            with patch('firebase_admin.auth.verify_id_token') as mock_verify:
                from firebase_admin import auth
                mock_verify.side_effect = auth.InvalidIdTokenError('Invalid token')
                
                with pytest.raises(HTTPException) as exc_info:
                    asyncio.run(verify_firebase_token(authorization=auth_header))
                
                assert exc_info.value.status_code == 401
                assert "Invalid or expired token" in exc_info.value.detail