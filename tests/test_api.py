import pytest


class TestAPIEndpoints:
    """Test suite for API endpoint integration - focuses on API-specific logic rather than business logic"""
    
    def test_root_endpoint(self):
        """Test the root health check endpoint"""
        from routes import router
        from main import app
        
        # Test the root endpoint function directly
        from routes import root
        import asyncio
        
        result = asyncio.run(root())
        assert result == {"message": "Cosmic Guru API is running"}
    
    def test_generate_chart_endpoint_integration(self):
        """Test that generate_chart_endpoint properly calls business logic and handles errors"""
        from routes import generate_chart_endpoint
        from models import BirthData
        from unittest.mock import patch, Mock
        import asyncio
        
        birth_data = BirthData(
            birthDate="1990-01-01",
            birthTime="12:00",
            latitude=40.7128,
            longitude=-74.0060
        )
        
        # Mock the business logic function to test integration
        with patch('routes.generate_birth_chart') as mock_generate:
            mock_chart = Mock()
            mock_chart.model_dump.return_value = {
                'planets': {},
                'houses': {},
                'aspects': [],
                'sunSign': {'name': 'Cap'},
                'moonSign': {'name': 'Gem'},
                'ascendant': {'name': 'Leo'},
                'chartSvg': '<svg>test</svg>'
            }
            mock_generate.return_value = mock_chart
            
            # Test the endpoint function
            result = asyncio.run(generate_chart_endpoint(birth_data, {'uid': 'test-user'}))
            
            # Verify the business logic was called with correct data
            mock_generate.assert_called_once_with(birth_data)
            
            # Verify the result is returned correctly
            assert result == mock_chart
    
    def test_generate_chart_endpoint_stores_chart(self):
        """Test that generate_chart_endpoint automatically stores chart in user profile"""
        from routes import generate_chart_endpoint
        from models import BirthData
        from unittest.mock import patch, Mock
        import asyncio
        
        birth_data = BirthData(
            birthDate="1990-01-01",
            birthTime="12:00",
            latitude=40.7128,
            longitude=-74.0060
        )
        user = {'uid': 'test-user-123'}
        
        with patch('routes.generate_birth_chart') as mock_generate:
            with patch('routes.get_firestore_client') as mock_get_db:
                with patch('routes.profile_cache') as mock_cache:
                    # Setup mocks
                    mock_chart = Mock()
                    mock_chart_data = {'planets': {}, 'houses': {}}
                    mock_chart.model_dump.return_value = mock_chart_data
                    mock_generate.return_value = mock_chart
                    
                    mock_db = Mock()
                    mock_get_db.return_value = mock_db
                    mock_doc_ref = Mock()
                    mock_db.collection.return_value.document.return_value = mock_doc_ref
                    
                    # Test the endpoint
                    result = asyncio.run(generate_chart_endpoint(birth_data, user))
                    
                    # Verify chart generation
                    mock_generate.assert_called_once_with(birth_data)
                    assert result == mock_chart
                    
                    # Verify chart storage
                    mock_db.collection.assert_called_with('user_profiles')
                    mock_db.collection.return_value.document.assert_called_with('test-user-123')
                    mock_doc_ref.update.assert_called_once()
                    
                    # Verify cache invalidation
                    mock_cache.invalidate.assert_called_once_with('test-user-123')

    def test_analyze_personality_endpoint_integration(self):
        """Test that analyze_personality_endpoint properly calls business logic"""
        from routes import analyze_personality
        from models import AnalysisRequest
        from unittest.mock import patch, Mock
        import asyncio
        
        analysis_request = AnalysisRequest(
            birth_date="1990-01-01T00:00:00Z",
            birth_time="12:00",
            birth_location="New York, USA",
            latitude=40.7128,
            longitude=-74.0060
        )
        
        # Test when Claude client is not available
        with patch('routes.claude_client', None):
            with pytest.raises(Exception):  # Should raise HTTPException
                asyncio.run(analyze_personality(analysis_request, {'uid': 'test'}))
        
        # Test when Claude client is available
        mock_user = {'uid': 'test-user', 'email': 'test@example.com'}
        
        with patch('routes.claude_client') as mock_claude:
            with patch('routes.generate_birth_chart') as mock_chart:
                # Setup mocks
                mock_chart_result = Mock()
                mock_chart_result.planets = {}  # Should be dict, not list
                mock_chart_result.aspects = []
                mock_chart.return_value = mock_chart_result
                
                # Mock TextBlock properly
                from anthropic.types import TextBlock
                mock_text_block = Mock(spec=TextBlock)
                mock_text_block.text = '{"overview": "test", "strengths": [], "challenges": [], "relationships": "test", "career": "test", "lifePath": "test"}'
                mock_claude.messages.create.return_value = Mock(
                    content=[mock_text_block]
                )
                
                # Test the endpoint function
                result = asyncio.run(analyze_personality(analysis_request, mock_user))
                
                # Verify business logic was called
                mock_chart.assert_called_once()
                mock_claude.messages.create.assert_called_once()
    
    def test_analyze_personality_endpoint_stores_analysis(self):
        """Test that analyze_personality_endpoint automatically stores analysis in user profile"""
        from routes import analyze_personality
        from models import AnalysisRequest
        from unittest.mock import patch, Mock
        import asyncio
        
        analysis_request = AnalysisRequest(
            birth_date="1990-01-01T00:00:00Z",
            birth_time="12:00",
            birth_location="New York, USA",
            latitude=40.7128,
            longitude=-74.0060
        )
        user = {'uid': 'test-user-123'}
        
        with patch('routes.claude_client') as mock_claude:
            with patch('routes.generate_birth_chart') as mock_chart:
                with patch('routes.get_firestore_client') as mock_get_db:
                    with patch('routes.profile_cache') as mock_cache:
                        # Setup mocks
                        mock_chart_result = Mock()
                        mock_chart_result.planets = {}
                        mock_chart_result.aspects = []
                        mock_chart.return_value = mock_chart_result
                        
                        mock_analysis_data = {
                            "overview": "test overview",
                            "strengths": [],
                            "challenges": [],
                            "relationships": "test relationships",
                            "career": "test career", 
                            "lifePath": "test life path"
                        }
                        
                        # Mock TextBlock properly  
                        import json
                        from anthropic.types import TextBlock
                        mock_text_block = Mock(spec=TextBlock)
                        mock_text_block.text = json.dumps(mock_analysis_data)
                        mock_claude.messages.create.return_value = Mock(
                            content=[mock_text_block]
                        )
                        
                        mock_db = Mock()
                        mock_get_db.return_value = mock_db
                        mock_doc_ref = Mock()
                        mock_db.collection.return_value.document.return_value = mock_doc_ref
                        
                        # Test the endpoint
                        with patch('json.loads', return_value=mock_analysis_data):
                            result = asyncio.run(analyze_personality(analysis_request, user))
                        
                        # Verify analysis storage
                        mock_db.collection.assert_called_with('user_profiles')
                        mock_db.collection.return_value.document.assert_called_with('test-user-123')
                        mock_doc_ref.update.assert_called_once()
                        
                        # Verify cache invalidation
                        mock_cache.invalidate.assert_called_once_with('test-user-123')

    def test_migrate_profile_endpoint_success(self):
        """Test successful profile migration"""
        from routes import migrate_profile_data
        from unittest.mock import patch, Mock
        import asyncio
        
        request_data = {'anonymous_uid': 'anonymous-user-123'}
        auth_user = {'uid': 'auth-user-456'}
        
        with patch('routes.get_firestore_client') as mock_get_db:
            with patch('routes.validate_database_availability') as mock_validate:
                with patch('routes.profile_cache') as mock_cache:
                    # Setup mocks
                    mock_db = Mock()
                    mock_get_db.return_value = mock_db
                    
                    # Mock anonymous profile with data
                    mock_anon_doc = Mock()
                    mock_anon_doc.exists = True
                    mock_anon_doc.to_dict.return_value = {
                        'astrological_chart': {'planets': {}, 'houses': {}},
                        'personality_analysis': {'overview': 'test analysis'}
                    }
                    
                    # Mock authenticated profile
                    mock_auth_doc = Mock()
                    mock_auth_doc.exists = True
                    
                    mock_db.collection.return_value.document.side_effect = [
                        Mock(get=Mock(return_value=mock_anon_doc)),  # anonymous profile
                        Mock(update=Mock(), get=Mock(return_value=mock_auth_doc))  # auth profile
                    ]
                    
                    # Test the endpoint
                    result = asyncio.run(migrate_profile_data(request_data, auth_user))
                    
                    # Verify the result
                    assert result['message'] == 'Profile data migrated successfully'
                    assert 'astrological_chart' in result['migrated_fields']
                    assert 'personality_analysis' in result['migrated_fields']
                    
                    # Verify cache was invalidated
                    mock_cache.invalidate.assert_called_once_with('auth-user-456')
    
    def test_migrate_profile_endpoint_no_anonymous_profile(self):
        """Test migration when no anonymous profile exists"""
        from routes import migrate_profile_data
        from unittest.mock import patch, Mock
        import asyncio
        
        request_data = {'anonymous_uid': 'nonexistent-user'}
        auth_user = {'uid': 'auth-user-456'}
        
        with patch('routes.get_firestore_client') as mock_get_db:
            with patch('routes.validate_database_availability') as mock_validate:
                # Setup mocks
                mock_db = Mock()
                mock_get_db.return_value = mock_db
                
                # Mock anonymous profile doesn't exist
                mock_anon_doc = Mock()
                mock_anon_doc.exists = False
                
                mock_db.collection.return_value.document.return_value.get.return_value = mock_anon_doc
                
                # Test the endpoint
                result = asyncio.run(migrate_profile_data(request_data, auth_user))
                
                # Verify the result
                assert result['message'] == 'No data to migrate'
    
    def test_migrate_profile_endpoint_missing_anonymous_uid(self):
        """Test migration endpoint with missing anonymous_uid"""
        from routes import migrate_profile_data
        import asyncio
        
        request_data = {}  # Missing anonymous_uid
        auth_user = {'uid': 'auth-user-456'}
        
        with pytest.raises(Exception):  # Should raise HTTPException
            asyncio.run(migrate_profile_data(request_data, auth_user))