import pytest
import sys
import os
from unittest.mock import MagicMock

# Add the backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Note: TestClient removed in favor of direct function testing
# This avoids httpx/starlette compatibility issues while providing better test isolation

@pytest.fixture
def mock_verify_firebase_token():
    """Mock function for authentication dependency"""
    return {
        "uid": "test_user_123",
        "email": "test@example.com",
        "decoded_token": {"uid": "test_user_123"}
    }

@pytest.fixture
def valid_birth_data():
    """Standard birth data for testing"""
    return {
        "birthDate": "1990-01-01",
        "birthTime": "12:00",
        "latitude": 40.7128,
        "longitude": -74.0060,
        "cityName": "New York",
        "countryName": "USA",
        "timezone": "America/New_York"
    }

@pytest.fixture
def valid_user():
    """Valid authenticated user for testing"""
    return {
        'user_id': 'test-user-123',
        'email': 'test@example.com',
        'firebase': {
            'sign_in_provider': 'google.com'
        }
    }

@pytest.fixture
def anonymous_user():
    """Anonymous user for testing"""
    return {
        'user_id': 'anonymous-user-123',
        'firebase': {
            'sign_in_provider': 'anonymous'
        }
    }

@pytest.fixture
def mock_firestore_db():
    """Mock Firestore database"""
    mock_doc_ref = MagicMock()
    mock_collection = MagicMock()
    mock_db = MagicMock()
    
    mock_db.collection.return_value = mock_collection
    mock_collection.document.return_value = mock_doc_ref
    
    return mock_db, mock_collection, mock_doc_ref