import pytest
from datetime import datetime
from unittest.mock import Mock, patch
from fastapi import HTTPException

from profile_logic import (
    validate_database_availability, create_user_profile_data, save_profile_to_database,
    get_profile_from_database, validate_profile_creation_request, format_profile_response
)
from models import ProfileCreationRequest, UserProfile


class TestProfileBusinessLogic:
    """Test suite for profile business logic functions"""
    
    def test_validate_database_availability_success(self):
        """Test database validation with available database"""
        mock_db = Mock()
        
        # Should not raise any exception
        validate_database_availability(mock_db)
    
    def test_validate_database_availability_failure(self):
        """Test database validation with unavailable database"""
        with pytest.raises(HTTPException) as exc_info:
            validate_database_availability(None)
        
        assert exc_info.value.status_code == 500
        assert "Database not available" in exc_info.value.detail
    
    def test_validate_profile_creation_request_valid(self):
        """Test profile creation request validation with valid data"""
        valid_request = ProfileCreationRequest(
            birth_date=datetime(1990, 1, 1),
            birth_time="12:00",
            latitude=40.7128,
            longitude=-74.0060,
            timezone="America/New_York"
        )
        
        # Should not raise any exception
        validate_profile_creation_request(valid_request)
    
    def test_validate_profile_creation_request_invalid_latitude(self):
        """Test profile creation request validation with invalid latitude"""
        invalid_request = ProfileCreationRequest(
            birth_date=datetime(1990, 1, 1),
            birth_time="12:00",
            latitude=95.0,  # Invalid - outside range
            longitude=-74.0060,
            timezone="America/New_York"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            validate_profile_creation_request(invalid_request)
        
        assert exc_info.value.status_code == 400
        assert "Latitude must be between -90 and 90" in exc_info.value.detail
    
    def test_validate_profile_creation_request_invalid_longitude(self):
        """Test profile creation request validation with invalid longitude"""
        invalid_request = ProfileCreationRequest(
            birth_date=datetime(1990, 1, 1),
            birth_time="12:00",
            latitude=40.7128,
            longitude=200.0,  # Invalid - outside range
            timezone="America/New_York"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            validate_profile_creation_request(invalid_request)
        
        assert exc_info.value.status_code == 400
        assert "Longitude must be between -180 and 180" in exc_info.value.detail
    
    def test_validate_profile_creation_request_invalid_time_format(self):
        """Test profile creation request validation with invalid time format"""
        invalid_request = ProfileCreationRequest(
            birth_date=datetime(1990, 1, 1),
            birth_time="25:70",  # Invalid time
            latitude=40.7128,
            longitude=-74.0060,
            timezone="America/New_York"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            validate_profile_creation_request(invalid_request)
        
        assert exc_info.value.status_code == 400
        assert "Birth time must be in HH:MM format" in exc_info.value.detail
    
    @patch('profile_logic.get_timezone_from_coordinates')
    def test_create_user_profile_data(self, mock_timezone):
        """Test creating user profile data from request"""
        mock_timezone.return_value = "America/New_York"
        
        profile_request = ProfileCreationRequest(
            birth_date=datetime(1990, 1, 1),
            birth_time="12:00",
            latitude=40.7128,
            longitude=-74.0060,
            timezone="America/New_York"
        )
        
        profile = create_user_profile_data(
            user_id="test-user-123",
            email="test@example.com",
            profile_request=profile_request
        )
        
        assert profile.uid == "test-user-123"
        assert profile.email == "test@example.com"
        assert profile.birth_date == datetime(1990, 1, 1)
        assert profile.birth_time == "12:00"
        assert profile.birth_location == "Lat: 40.7128, Lon: -74.006"
        assert profile.latitude == 40.7128
        assert profile.longitude == -74.0060
        assert profile.timezone == "America/New_York"
        assert profile.created_at is not None
        assert profile.updated_at is not None
        
        mock_timezone.assert_called_once_with(40.7128, -74.0060)
    
    def test_save_profile_to_database(self):
        """Test saving profile to database"""
        mock_db = Mock()
        mock_collection = Mock()
        mock_doc_ref = Mock()
        
        mock_db.collection.return_value = mock_collection
        mock_collection.document.return_value = mock_doc_ref
        
        profile = UserProfile(
            uid="test-user-123",
            email="test@example.com",
            birth_date=datetime(1990, 1, 1),
            birth_time="12:00",
            birth_location="New York, NY",
            latitude=40.7128,
            longitude=-74.0060,
            timezone="America/New_York",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            astrological_chart=None,
            personality_analysis=None
        )
        
        save_profile_to_database(mock_db, "test-user-123", profile)
        
        mock_db.collection.assert_called_once_with('user_profiles')
        mock_collection.document.assert_called_once_with('test-user-123')
        mock_doc_ref.set.assert_called_once_with(profile.model_dump())
    
    def test_get_profile_from_database_success(self):
        """Test getting profile from database successfully"""
        mock_db = Mock()
        mock_collection = Mock()
        mock_doc_ref = Mock()
        mock_doc = Mock()
        
        mock_db.collection.return_value = mock_collection
        mock_collection.document.return_value = mock_doc_ref
        mock_doc_ref.get.return_value = mock_doc
        mock_doc.exists = True
        
        profile_data = {
            'uid': 'test-user-123',
            'email': 'test@example.com',
            'birth_date': datetime(1990, 1, 1),
            'birth_time': '12:00',
            'birth_location': 'New York, NY',
            'latitude': 40.7128,
            'longitude': -74.0060,
            'timezone': 'America/New_York',
            'created_at': datetime.now(),
            'updated_at': datetime.now(),
            'astrological_chart': None,
            'personality_analysis': None
        }
        mock_doc.to_dict.return_value = profile_data
        
        profile = get_profile_from_database(mock_db, "test-user-123")
        
        assert profile.uid == "test-user-123"
        assert profile.email == "test@example.com"
        mock_db.collection.assert_called_once_with('user_profiles')
        mock_collection.document.assert_called_once_with('test-user-123')
        mock_doc_ref.get.assert_called_once()
    
    def test_get_profile_from_database_not_found(self):
        """Test getting profile from database when not found"""
        mock_db = Mock()
        mock_collection = Mock()
        mock_doc_ref = Mock()
        mock_doc = Mock()
        
        mock_db.collection.return_value = mock_collection
        mock_collection.document.return_value = mock_doc_ref
        mock_doc_ref.get.return_value = mock_doc
        mock_doc.exists = False
        
        with pytest.raises(HTTPException) as exc_info:
            get_profile_from_database(mock_db, "nonexistent-user")
        
        assert exc_info.value.status_code == 404
        assert "Profile not found" in exc_info.value.detail
    
    def test_format_profile_response(self):
        """Test formatting profile for API response"""
        profile = UserProfile(
            uid="test-user-123",
            email="test@example.com",
            birth_date=datetime(1990, 1, 1),
            birth_time="12:00",
            birth_location="New York, NY",
            latitude=40.7128,
            longitude=-74.0060,
            timezone="America/New_York",
            created_at=datetime(2023, 1, 1, 12, 0, 0),
            updated_at=datetime(2023, 1, 1, 12, 0, 0),
            astrological_chart=None,
            personality_analysis=None
        )
        
        formatted = format_profile_response(profile)
        
        assert formatted['uid'] == "test-user-123"
        assert formatted['email'] == "test@example.com"
        assert formatted['birth_date'] == "1990-01-01T00:00:00"
        assert formatted['created_at'] == "2023-01-01T12:00:00"
        assert formatted['updated_at'] == "2023-01-01T12:00:00"
        assert formatted['astrological_chart'] is None
        assert formatted['personality_analysis'] is None


class TestProfileCache:
    """Test suite for profile caching functionality"""
    
    def test_profile_cache_stores_and_retrieves_data(self):
        """Test that profile cache stores and retrieves data correctly"""
        from routes import ProfileCache
        
        cache = ProfileCache(ttl_minutes=30)
        test_profile = {
            'uid': 'test-user-123',
            'email': 'test@example.com',
            'birth_date': '1990-01-01T00:00:00'
        }
        
        # Initially empty
        assert cache.get('test-user-123') is None
        
        # Store data
        cache.set('test-user-123', test_profile)
        
        # Retrieve data
        cached_profile = cache.get('test-user-123')
        assert cached_profile == test_profile
    
    def test_profile_cache_expires_after_ttl(self):
        """Test that profile cache expires after TTL"""
        from routes import ProfileCache
        import time
        
        cache = ProfileCache(ttl_minutes=0.01)  # 0.6 seconds for testing
        test_profile = {'uid': 'test-user-123'}
        
        # Store data
        cache.set('test-user-123', test_profile)
        assert cache.get('test-user-123') == test_profile
        
        # Wait for expiration
        time.sleep(1)
        
        # Should be expired
        assert cache.get('test-user-123') is None
    
    def test_profile_cache_invalidate(self):
        """Test that profile cache invalidate removes data"""
        from routes import ProfileCache
        
        cache = ProfileCache(ttl_minutes=30)
        test_profile = {'uid': 'test-user-123'}
        
        # Store data
        cache.set('test-user-123', test_profile)
        assert cache.get('test-user-123') == test_profile
        
        # Invalidate
        cache.invalidate('test-user-123')
        assert cache.get('test-user-123') is None
    
    def test_profile_cache_clear(self):
        """Test that profile cache clear removes all data"""
        from routes import ProfileCache
        
        cache = ProfileCache(ttl_minutes=30)
        
        # Store multiple profiles
        cache.set('user-1', {'uid': 'user-1'})
        cache.set('user-2', {'uid': 'user-2'})
        
        assert cache.get('user-1') is not None
        assert cache.get('user-2') is not None
        
        # Clear all
        cache.clear()
        
        assert cache.get('user-1') is None
        assert cache.get('user-2') is None