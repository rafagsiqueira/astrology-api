import unittest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import sys
import asyncio

# Mock semantic_kernel modules before any routes import
sys.modules['semantic_kernel'] = Mock()
sys.modules['semantic_kernel.connectors.ai.open_ai'] = Mock()
sys.modules['semantic_kernel.contents'] = Mock()
sys.modules['semantic_kernel.functions'] = Mock()


class TextBlock:
    """Simple stand-in for anthropic.types.TextBlock used in legacy tests."""

    def __init__(self, text: str = ""):
        self.text = text

class TestAPIEndpoints(unittest.TestCase):
    """Test suite for API endpoint integration - focuses on API-specific logic rather than business logic"""

    def setUp(self):
        self.weather_patcher = patch('routes.fetch_daily_weather_forecast', return_value=[])
        self.mock_weather = self.weather_patcher.start()

        async def immediate_to_thread(func, *args, **kwargs):
            return func(*args, **kwargs)

        self.to_thread_patcher = patch('routes.asyncio.to_thread', side_effect=immediate_to_thread)
        self.mock_to_thread = self.to_thread_patcher.start()

        self.pref_location_patcher = patch('routes._get_preferred_forecast_location', return_value=None)
        self.mock_pref_location = self.pref_location_patcher.start()

        self.cached_transits_patcher = patch('routes._load_cached_transits', return_value={})
        self.mock_cached_transits = self.cached_transits_patcher.start()

        self.store_transit_patcher = patch('routes._store_transit_document')
        self.mock_store_transit = self.store_transit_patcher.start()

        self.validate_db_patcher = patch('routes.validate_database_availability', return_value=None)
        self.mock_validate_db = self.validate_db_patcher.start()

        self.firestore_client_patcher = patch('routes.get_firestore_client', return_value=Mock())
        self.mock_firestore_client = self.firestore_client_patcher.start()

        self.weather_range_patcher = patch('routes._fetch_weather_range', new=AsyncMock(return_value={}))
        self.mock_weather_range = self.weather_range_patcher.start()

        self.generate_tts_patcher = patch(
            'routes.generate_tts_audio',
            return_value=('daily_transits/test-user-123/2024-01-01/message.mp3', 'mp3'),
        )
        self.mock_generate_tts = self.generate_tts_patcher.start()

        self.analytics_patcher = patch('routes.get_analytics_service', return_value=AsyncMock())
        self.mock_analytics = self.analytics_patcher.start()

    def tearDown(self):
        self.weather_patcher.stop()
        self.to_thread_patcher.stop()
        self.pref_location_patcher.stop()
        self.cached_transits_patcher.stop()
        self.store_transit_patcher.stop()
        self.validate_db_patcher.stop()
        self.firestore_client_patcher.stop()
        self.weather_range_patcher.stop()
        self.generate_tts_patcher.stop()
        self.analytics_patcher.stop()

    def test_root_endpoint(self):
        """Test the root health check endpoint"""
        from routes import root
        result = asyncio.run(root())
        self.assertEqual(result, {"message": "Avra API is running"})

    def test_generate_chart_endpoint_integration(self):
        """Test that generate_chart_endpoint properly calls business logic and handles errors"""
        from routes import generate_chart_endpoint
        from models import BirthData
        
        birth_data = BirthData(
            birth_date="1990-01-01",
            birth_time="12:00",
            latitude=40.7128,
            longitude=-74.0060
        )
        
        with patch('routes.generate_birth_chart') as mock_generate:
            with patch('routes.build_birth_chart_context') as mock_build_context:
                with patch('routes.get_gemini_client') as mock_get_gemini:
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
                        mock_build_context.return_value = ("cached_context", "user_context")
                        
                        mock_response = Mock()
                        # Valid JSON matching ChartAnalysis model
                        mock_response.text = '''
                        {
                            "sun": {"influence": "test", "traits": []},
                            "moon": {"influence": "test", "traits": []},
                            "ascendant": {"influence": "test", "traits": []},
                            "mercury": {"influence": "test", "traits": []},
                            "venus": {"influence": "test", "traits": []},
                            "mars": {"influence": "test", "traits": []},
                            "jupiter": {"influence": "test", "traits": []},
                            "saturn": {"influence": "test", "traits": []},
                            "uranus": {"influence": "test", "traits": []},
                            "neptune": {"influence": "test", "traits": []},
                            "pluto": {"influence": "test", "traits": []}
                        }
                        '''
                        mock_response.usage_metadata = Mock(prompt_token_count=100, candidates_token_count=50)
                        
                        mock_gemini = Mock()
                        mock_gemini.models.generate_content.return_value = mock_response
                        mock_get_gemini.return_value = mock_gemini
                        
                        result = asyncio.run(generate_chart_endpoint(birth_data, {'uid': 'test-user'}))
                        
                        mock_generate.assert_called_once_with(birth_data)
                        self.assertEqual(result, mock_chart)
                        self.assertIsNotNone(mock_chart.analysis)

    def test_generate_chart_endpoint_stores_chart(self):
        """Test that generate_chart_endpoint returns the chart (note: current implementation doesn't store)"""
        from routes import generate_chart_endpoint
        from models import BirthData
        
        birth_data = BirthData(
            birth_date="1990-01-01",
            birth_time="12:00",
            latitude=40.7128,
            longitude=-74.0060
        )
        user = {'uid': 'test-user-123'}
        
        with patch('routes.generate_birth_chart') as mock_generate:
            with patch('routes.build_birth_chart_context') as mock_build_context:
                with patch('routes.get_gemini_client') as mock_get_gemini:
                        mock_chart = Mock()
                        mock_chart_data = {'planets': {}, 'houses': {}}
                        mock_chart.model_dump.return_value = mock_chart_data
                        mock_generate.return_value = mock_chart
                        mock_build_context.return_value = ("cached_context", "user_context")
                        
                        mock_response = Mock()
                        mock_response.text = '''
                        {
                            "sun": {"influence": "test", "traits": []},
                            "moon": {"influence": "test", "traits": []},
                            "ascendant": {"influence": "test", "traits": []},
                            "mercury": {"influence": "test", "traits": []},
                            "venus": {"influence": "test", "traits": []},
                            "mars": {"influence": "test", "traits": []},
                            "jupiter": {"influence": "test", "traits": []},
                            "saturn": {"influence": "test", "traits": []},
                            "uranus": {"influence": "test", "traits": []},
                            "neptune": {"influence": "test", "traits": []},
                            "pluto": {"influence": "test", "traits": []}
                        }
                        '''
                        mock_response.usage_metadata = Mock(prompt_token_count=100, candidates_token_count=50)
                        
                        mock_gemini = Mock()
                        mock_gemini.models.generate_content.return_value = mock_response
                        mock_get_gemini.return_value = mock_gemini
                        
                        result = asyncio.run(generate_chart_endpoint(birth_data, user))
                        
                        mock_generate.assert_called_once_with(birth_data)
                        self.assertEqual(result, mock_chart)
                        self.assertIsNotNone(mock_chart.analysis)

    def test_analyze_personality_endpoint_integration(self):
        """Test that analyze_personality_endpoint properly calls business logic"""
        from routes import analyze_personality
        from models import AnalysisRequest
        
        analysis_request = AnalysisRequest(
            birth_date="1990-01-01",
            birth_time="12:00",
            latitude=40.7128,
            longitude=-74.0060
        )
        
        with patch('routes.get_gemini_client', return_value=None):
            with self.assertRaises(Exception):
                asyncio.run(analyze_personality(analysis_request, {'uid': 'test'}))
        
        mock_user = {'uid': 'test-user', 'email': 'test@example.com'}
        
        with patch('routes.get_gemini_client') as mock_get_gemini:
            with patch('contexts.generate_birth_chart') as mock_chart:
                mock_chart_result = Mock()
                mock_chart_result.planets = {}
                mock_chart_result.aspects = []
                mock_chart.return_value = mock_chart_result
                
                personality_payload = (
                    '{'
                    '"overview": "Test overview",\n'
                    '"personality_traits": {\n'
                    '  "description": "Test personality traits description",\n'
                    '  "key_traits": ["Analytical", "Creative"]\n'
                    '},\n'
                    '"emotional_nature": {\n'
                    '  "description": "Test emotional nature description",\n'
                    '  "emotional_characteristics": ["Sensitive", "Intuitive"]\n'
                    '},\n'
                    '"communication_and_intellect": {\n'
                    '  "description": "Test communication description",\n'
                    '  "communication_strengths": ["Articulate", "Thoughtful"]\n'
                    '},\n'
                    '"relationships_and_love": {\n'
                    '  "description": "Test relationships description",\n'
                    '  "relationship_dynamics": ["Loyal", "Supportive"]\n'
                    '},\n'
                    '"career_and_purpose": {\n'
                    '  "description": "Test career description",\n'
                    '  "career_potential": ["Leadership", "Innovation"]\n'
                    '},\n'
                    '"strengths_and_challenges": {\n'
                    '  "strengths": ["Determination", "Creativity"],\n'
                    '  "challenges": ["Perfectionism", "Overthinking"]\n'
                    '},\n'
                    '"life_path": {\n'
                    '  "overview": "Test life path overview",\n'
                    '  "key_development_areas": ["Self-confidence", "Communication"]\n'
                    '}\n'
                    '}'
                )

                mock_response = Mock()
                mock_response.text = personality_payload
                mock_response.usage_metadata = Mock(prompt_token_count=100, candidates_token_count=50)
                
                mock_gemini = Mock()
                mock_gemini.models.generate_content.return_value = mock_response
                mock_get_gemini.return_value = mock_gemini
                
                asyncio.run(analyze_personality(analysis_request, mock_user))
                
                mock_chart.assert_called_once()
                mock_get_gemini.assert_called_once()
                mock_gemini.models.generate_content.assert_called_once()

    def test_analyze_personality_endpoint_returns_analysis(self):
        """Test that analyze_personality_endpoint returns proper analysis"""
        from routes import analyze_personality
        from models import AnalysisRequest
        
        analysis_request = AnalysisRequest(
            birth_date="1990-01-01",
            birth_time="12:00",
            latitude=40.7128,
            longitude=-74.0060
        )
        user = {'uid': 'test-user-123'}
        
        with patch('routes.get_gemini_client') as mock_get_gemini:
            with patch('routes.build_personality_context') as mock_build_context:
                    mock_build_context.return_value = ("Mocked system", "Mocked user message")
                    
                    mock_response = Mock()
                    mock_response.text = '''{
                        "overview": "Test analysis overview",
                        "personality_traits": { "description": "d", "key_traits": [] },
                        "emotional_nature": { "description": "d", "emotional_characteristics": [] },
                        "communication_and_intellect": { "description": "d", "communication_strengths": [] },
                        "relationships_and_love": { "description": "d", "relationship_dynamics": [] },
                        "career_and_purpose": { "description": "d", "career_potential": [] },
                        "strengths_and_challenges": { "strengths": [], "challenges": [] },
                        "life_path": { "overview": "d", "key_development_areas": [] }
                    }'''
                    mock_response.usage_metadata = Mock(prompt_token_count=100, candidates_token_count=50)
                    
                    mock_gemini = Mock()
                    mock_gemini.models.generate_content.return_value = mock_response
                    mock_get_gemini.return_value = mock_gemini
                    
                    mock_get_gemini.return_value = mock_gemini
                    
                    result = asyncio.run(analyze_personality(analysis_request, user))
                    
                    self.assertEqual(result.overview, "Test analysis overview")
                    mock_get_gemini.assert_called_once()
                    mock_build_context.assert_called_once_with(analysis_request)
                    mock_gemini.models.generate_content.assert_called_once()

    def test_analyze_relationship_success(self):
        """Test successful relationship analysis with valid data"""
        from routes import analyze_relationship
        from models import RelationshipAnalysisRequest, BirthData, RelationshipAnalysis
        
        person1_birth_data = BirthData(
            birth_date="1990-01-01",
            birth_time="12:00",
            latitude=40.7128,
            longitude=-74.0060
        )
        person2_birth_data = BirthData(
            birth_date="1992-05-15",
            birth_time="14:30",
            latitude=34.0522,
            longitude=-118.2437
        )
        request = RelationshipAnalysisRequest(
            person1=person1_birth_data,
            person2=person2_birth_data,
            relationship_type="romantic"
        )
        auth_user = {'uid': 'test-user-123'}
        
        with patch('routes.build_relationship_context') as mock_build_context:
            with patch('routes.get_gemini_client') as mock_get_gemini:
                with patch('routes.create_astrological_subject') as mock_create_subject:
                    with patch('routes.RelationshipScoreFactory') as mock_score_factory:
                        with patch('routes.generate_birth_chart') as mock_generate_chart:
                            mock_build_context.return_value = ("Mocked system", "Mocked user message")
                            mock_create_subject.return_value = Mock()
                            mock_score_factory.return_value.get_relationship_score.return_value = Mock(score_value=85, score_description="High", is_destiny_sign=True, aspects=[])
                            mock_chart = Mock()
                            mock_chart.light_svg = "<svg></svg>"
                            mock_chart.dark_svg = "<svg></svg>"
                            mock_generate_chart.return_value = mock_chart
                            
                            mock_response = Mock()
                            mock_response.text = '''{
                                "score": 85,
                                "overview": "This is a powerful astrological connection with strong karmic ties.",
                                "compatibility_level": "Very High",
                                "destiny_signs": "Strong karmic connections present",
                                "relationship_aspects": ["Sun conjunction Moon", "Venus trine Mars"],
                                "strengths": ["Deep emotional understanding", "Natural compatibility"],
                                "challenges": ["Intensity may be overwhelming", "Need to maintain independence"],
                                "areas_for_growth": ["Embrace the connection while maintaining individual growth"]
                            }'''
                            mock_response.usage_metadata = Mock(prompt_token_count=100, candidates_token_count=50)
                            
                            mock_gemini = Mock()
                            mock_gemini.models.generate_content.return_value = mock_response
                            mock_get_gemini.return_value = mock_gemini
                            
                            result = asyncio.run(analyze_relationship(request, auth_user))
                            
                            self.assertEqual(result.score, 85)
                            self.assertEqual(result.overview, "This is a powerful astrological connection with strong karmic ties.")
                            self.assertEqual(result.compatibility_level, "Very High")
                            self.assertEqual(result.destiny_signs, "Strong karmic connections present")
                            self.assertEqual(result.relationship_aspects, ["Sun conjunction Moon", "Venus trine Mars"])
                            self.assertEqual(result.strengths, ["Deep emotional understanding", "Natural compatibility"])
                            self.assertEqual(result.challenges, ["Intensity may be overwhelming", "Need to maintain independence"])
                            self.assertEqual(result.areas_for_growth, ["Embrace the connection while maintaining individual growth"])

    def test_analyze_relationship_structured_analysis_error(self):
        """Test relationship analysis when structured analysis fails"""
        from routes import analyze_relationship
        from models import RelationshipAnalysisRequest, BirthData
        
        person1_birth_data = BirthData(
            birth_date="1990-01-01",
            birth_time="12:00",
            latitude=40.7128,
            longitude=-74.0060
        )
        person2_birth_data = BirthData(
            birth_date="1992-05-15",
            birth_time="14:30",
            latitude=34.0522,
            longitude=-118.2437
        )
        request = RelationshipAnalysisRequest(
            person1=person1_birth_data,
            person2=person2_birth_data,
            relationship_type="romantic"
        )
        auth_user = {'uid': 'test-user-123'}
        
        with patch('routes.build_relationship_context') as mock_build_context:
            with patch('routes.get_gemini_client') as mock_get_gemini:
                with patch('routes.create_astrological_subject'):
                    mock_build_context.return_value = ("Mocked system", "Mocked user message")
                    mock_get_gemini.return_value = Mock()
                    # Make configured gemini call raise exception? Or return invalid JSON
                    mock_gemini = Mock()
                    mock_response = Mock()
                    mock_response.text = "Invalid JSON"
                    mock_gemini.models.generate_content.return_value = mock_response
                    mock_get_gemini.return_value = mock_gemini
                    
                    # model_validate_json will raise validation error on invalid JSON
                    with self.assertRaises(Exception):
                        asyncio.run(analyze_relationship(request, auth_user))

    def test_analyze_relationship_api_key_unavailable(self):
        """Test relationship analysis when API key is not available"""
        from routes import analyze_relationship
        from models import RelationshipAnalysisRequest, BirthData, RelationshipAnalysis
        
        person1_birth_data = BirthData(
            birth_date="1990-01-01",
            birth_time="12:00",
            latitude=40.7128,
            longitude=-74.0060
        )
        person2_birth_data = BirthData(
            birth_date="1992-05-15",
            birth_time="14:30",
            latitude=34.0522,
            longitude=-118.2437
        )
        request = RelationshipAnalysisRequest(
            person1=person1_birth_data,
            person2=person2_birth_data,
            relationship_type="romantic"
        )
        auth_user = {'uid': 'test-user-123'}
        
        with patch('routes.build_relationship_context') as mock_build_context:
            with patch('routes.get_gemini_client') as mock_get_gemini:
                 
                    mock_build_context.return_value = ("Mocked system", "Mocked user message")
                    mock_get_gemini.return_value = None
                    
                    with self.assertRaises(Exception):
                        asyncio.run(analyze_relationship(request, auth_user))

    def test_analyze_relationship_calculation_error(self):
        """Test relationship analysis when score calculation fails"""
        from routes import analyze_relationship
        from models import RelationshipAnalysisRequest, BirthData
        
        person1_birth_data = BirthData(
            birth_date="1990-01-01",
            birth_time="12:00",
            latitude=40.7128,
            longitude=-74.0060
        )
        person2_birth_data = BirthData(
            birth_date="1992-05-15",
            birth_time="14:30",
            latitude=34.0522,
            longitude=-118.2437
        )
        request = RelationshipAnalysisRequest(
            person1=person1_birth_data,
            person2=person2_birth_data,
            relationship_type="romantic"
        )
        auth_user = {'uid': 'test-user-123'}
        
        with patch('routes.build_relationship_context', side_effect=ValueError("Failed to build context")):
            with self.assertRaises(Exception):
                asyncio.run(analyze_relationship(request, auth_user))

    def test_analyze_relationship_low_score(self):
        """Test relationship analysis with low compatibility score"""
        from routes import analyze_relationship
        from models import RelationshipAnalysisRequest, BirthData, RelationshipAnalysis
        
        person1_birth_data = BirthData(
            birth_date="1990-01-01",
            birth_time="12:00",
            latitude=40.7128,
            longitude=-74.0060
        )
        person2_birth_data = BirthData(
            birth_date="1995-12-25",
            birth_time="06:00",
            latitude=51.5074,
            longitude=-0.1278
        )
        request = RelationshipAnalysisRequest(
            person1=person1_birth_data,
            person2=person2_birth_data,
            relationship_type="romantic"
        )
        auth_user = {'uid': 'test-user-123'}
        
        with patch('routes.build_relationship_context') as mock_build_context:
            with patch('routes.get_gemini_client') as mock_get_gemini:
                with patch('routes.create_astrological_subject') as mock_create_subject:
                    with patch('routes.RelationshipScoreFactory') as mock_score_factory:
                        with patch('routes.generate_birth_chart') as mock_generate_chart:
                            mock_build_context.return_value = ("Mocked system", "Mocked user message")
                            mock_create_subject.return_value = Mock()
                            mock_score_factory.return_value.get_relationship_score.return_value = Mock(score_value=35, score_description="Low", is_destiny_sign=False, aspects=[])
                            mock_chart = Mock()
                            mock_chart.light_svg = "https://test.com/chart.svg"
                            mock_generate_chart.return_value = mock_chart
                            
                            mock_response = Mock()
                            mock_response = Mock()
                            mock_response.text = '''{
                                "score": 35,
                                "overview": "This relationship may require significant effort to develop compatibility.",
                                "compatibility_level": "Low",
                                "destiny_signs": "No significant karmic connections",
                                "relationship_aspects": ["Limited harmonious aspects"],
                                "strengths": ["Opportunity for growth", "Learning from differences"],
                                "challenges": ["Different life approaches", "Communication barriers"],
                                "areas_for_growth": ["Focus on building understanding through patient communication"]
                            }'''
                            mock_response.usage_metadata = Mock(prompt_token_count=100, candidates_token_count=50)
                            
                            mock_gemini = Mock()
                            mock_gemini.models.generate_content.return_value = mock_response
                            mock_get_gemini.return_value = mock_gemini
                            
                            result = asyncio.run(analyze_relationship(request, auth_user))
                            
                            self.assertEqual(result.score, 35)
                            self.assertIn("significant effort", result.overview)

    def test_get_daily_transits_success(self):
        """Test successful daily transits request"""
        from routes import get_daily_transits
        from models import DailyTransitRequest, BirthData, CurrentLocation, HoroscopePeriod
        from datetime import datetime
        
        birth_data = BirthData(
            birth_date="1990-01-01",
            birth_time="12:00",
            latitude=40.7128,
            longitude=-74.0060
        )
        current_location = CurrentLocation(
            latitude=40.7128,
            longitude=-74.0060
        )
        request = DailyTransitRequest(
            birth_data=birth_data,
            current_location=current_location,
            target_date=datetime.now().isoformat(),
            period=HoroscopePeriod.day
        )
        auth_user = {'uid': 'test-user-123'}
        with patch('routes.get_gemini_client') as mock_get_gemini:
            with patch('routes.generate_transits') as mock_generate:
                with patch('routes.diff_transits') as mock_diff:
                    from models import DailyTransit, DailyTransitChange, TransitChanges, RetrogradeChanges
                    
                    mock_daily_transit = DailyTransit(
                        date=datetime.now(),
                        aspects=[],
                        retrograding=["Mercury"]
                    )
                    
                    mock_transit_change = DailyTransitChange(
                        date=datetime.now().strftime("%Y-%m-%d"),
                        aspects=TransitChanges(began=[], ended=[]),
                        retrogrades=RetrogradeChanges(began=["Mercury"], ended=[])
                    )
                    
                    mock_generate.return_value = [mock_daily_transit]
                    mock_diff.return_value = [mock_transit_change]

                    current_date_str = datetime.now().strftime("%Y-%m-%d")
                    
                    # Gemini returns parsed text directly if using response_schema, usually.
                    # But here we probably use plain text response and expect JSON? 
                    # routes.py uses `call_gemini_with_analytics`.
                    mock_response = Mock()
                    mock_response.text = f'[{{"date": "{current_date_str}", "message": "Today is a good day for reflection.", "audioscript": "Today is a good day for reflection. The planetary alignments suggest introspection and inner wisdom."}}]'
                    mock_response.usage_metadata = Mock(prompt_token_count=100, candidates_token_count=50)

                    mock_gemini = Mock()
                    mock_gemini.models.generate_content.return_value = mock_response
                    mock_get_gemini.return_value = mock_gemini

                    # We mock generate_tts_audio at class level, so no need to mock OpenAI audio stream here.

                    self.mock_weather_range.return_value = {
                        datetime.now().strftime("%Y-%m-%d"): {
                            "date": datetime.now().strftime("%Y-%m-%d"),
                            "condition_code": "Clear",
                            "symbol_name": "sun.max",
                            "max_temperature_c": 24.0,
                            "min_temperature_c": 15.0,
                            "precipitation_chance": 0.1,
                            "forecast_summary": "Sunny and bright."
                        }
                    }

                    result = asyncio.run(get_daily_transits(request, auth_user))

                    self.assertEqual(result.transits, [mock_daily_transit])
                    self.assertEqual(result.changes, [mock_transit_change])
                    self.assertIsNotNone(result.weather)
                    self.assertTrue(result.messages)
                    self.assertTrue(result.messages[0].audio_path)
                    mock_generate.assert_called_once()
                    mock_diff.assert_called_once_with([mock_daily_transit])
                    self.mock_generate_tts.assert_called()

    def test_get_daily_transits_invalid_date(self):
        """Test daily transits with invalid date format"""
        from routes import get_daily_transits
        from models import DailyTransitRequest, BirthData, CurrentLocation, HoroscopePeriod
        
        birth_data = BirthData(
            birth_date="1990-01-01",
            birth_time="12:00",
            latitude=40.7128,
            longitude=-74.0060
        )
        current_location = CurrentLocation(
            latitude=40.7128,
            longitude=-74.0060
        )
        request = DailyTransitRequest(
            birth_data=birth_data,
            current_location=current_location,
            target_date="invalid-date-format",
            period=HoroscopePeriod.day
        )
        auth_user = {'uid': 'test-user-123'}
        
        with self.assertRaises(Exception):
            asyncio.run(get_daily_transits(request, auth_user))

    def test_get_daily_transits_generate_error(self):
        """Test daily transits when generate_transits raises error"""
        from routes import get_daily_transits
        from models import DailyTransitRequest, BirthData, CurrentLocation, HoroscopePeriod
        
        birth_data = BirthData(
            birth_date="1990-01-01",
            birth_time="12:00",
            latitude=40.7128,
            longitude=-74.0060
        )
        current_location = CurrentLocation(
            latitude=40.7128,
            longitude=-74.0060
        )
        request = DailyTransitRequest(
            birth_data=birth_data,
            current_location=current_location,
            target_date="2024-01-01T00:00:00",
            period=HoroscopePeriod.day
        )
        auth_user = {'uid': 'test-user-123'}
        
        with patch('routes.generate_transits', side_effect=ValueError("Transit calculation failed")):
            with self.assertRaises(Exception):
                asyncio.run(get_daily_transits(request, auth_user))

    def test_get_daily_transits_diff_error(self):
        """Test daily transits when diff_transits raises error"""
        from routes import get_daily_transits
        from models import DailyTransitRequest, BirthData, CurrentLocation, HoroscopePeriod
        from datetime import datetime
        
        birth_data = BirthData(
            birth_date="1990-01-01",
            birth_time="12:00",
            latitude=40.7128,
            longitude=-74.0060
        )
        current_location = CurrentLocation(
            latitude=40.7128,
            longitude=-74.0060
        )
        request = DailyTransitRequest(
            birth_data=birth_data,
            current_location=current_location,
            target_date="2024-01-01T00:00:00",
            period=HoroscopePeriod.day
        )
        auth_user = {'uid': 'test-user-123'}
        
        with patch('routes.generate_transits') as mock_generate:
            with patch('routes.diff_transits', side_effect=ValueError("Diff calculation failed")):
                from models import DailyTransit
                
                mock_generate.return_value = [DailyTransit(
                    date=datetime(2024, 1, 1),
                    aspects=[],
                    retrograding=[]
                )]
                
                with self.assertRaises(Exception):
                    asyncio.run(get_daily_transits(request, auth_user))



    def test_get_daily_transits_unauthenticated_user(self):
        """Test daily transits endpoint with unauthenticated user"""
        from routes import get_daily_transits
        from models import DailyTransitRequest, BirthData, CurrentLocation, HoroscopePeriod
        
        birth_data = BirthData(
            birth_date="1990-01-01",
            birth_time="12:00",
            latitude=40.7128,
            longitude=-74.0060
        )
        current_location = CurrentLocation(
            latitude=40.7128,
            longitude=-74.0060
        )
        request = DailyTransitRequest(
            birth_data=birth_data,
            current_location=current_location,
            target_date="2024-01-01T00:00:00",
            period=HoroscopePeriod.day
        )
        
        with self.assertRaises(Exception):
            asyncio.run(get_daily_transits(request, {}))

    def test_get_daily_transits_valid_authenticated_user(self):
        """Test daily transits endpoint with valid authenticated user"""
        from routes import get_daily_transits
        from models import DailyTransitRequest, BirthData, CurrentLocation, HoroscopePeriod
        from datetime import datetime
        
        birth_data = BirthData(
            birth_date="1990-01-01",
            birth_time="12:00",
            latitude=40.7128,
            longitude=-74.0060
        )
        current_location = CurrentLocation(
            latitude=40.7128,
            longitude=-74.0060
        )
        request = DailyTransitRequest(
            birth_data=birth_data,
            current_location=current_location,
            target_date=datetime.now().isoformat(),
            period=HoroscopePeriod.day
        )
        
        auth_user = {
            'uid': 'test-user-123',
            'email': 'test@example.com',
            'name': 'Test User'
        }
        
        with patch('routes.get_gemini_client') as mock_get_gemini:
            with patch('routes.generate_transits') as mock_generate:
                with patch('routes.diff_transits') as mock_diff:
                    from models import DailyTransit, DailyTransitChange, TransitChanges, RetrogradeChanges
                    
                    mock_transit = DailyTransit(
                        date=datetime.now(),
                        aspects=[],
                        retrograding=[]
                    )
                    mock_change = DailyTransitChange(
                        date=datetime.now().strftime("%Y-%m-%d"),
                        aspects=TransitChanges(began=[], ended=[]),
                        retrogrades=RetrogradeChanges(began=[], ended=[])
                    )
                    mock_generate.return_value = [mock_transit]
                    mock_diff.return_value = [mock_change]

                    mock_response = Mock()
                    mock_response.text = '[{"date": "2024-01-01", "message": "Today is a good day for reflection.", "audioscript": "Today is a good day for reflection. The planetary alignments suggest introspection and inner wisdom."}]'
                    mock_response.usage_metadata = Mock(prompt_token_count=100, candidates_token_count=50)

                    mock_gemini = Mock()
                    mock_gemini.models.generate_content.return_value = mock_response
                    mock_get_gemini.return_value = mock_gemini

                    # Mock weather
                    self.mock_weather_range.return_value = {}

                    mock_usage = Mock()
                    mock_usage.input_tokens = 100
                    mock_usage.output_tokens = 50

                    
                    result = asyncio.run(get_daily_transits(request, auth_user))
                    
                    self.assertEqual(result.transits, [mock_transit])
                    self.assertEqual(result.changes, [mock_change])
                    mock_generate.assert_called_once()

    def test_get_daily_transits_missing_user_fields(self):
        """Test daily transits endpoint with user missing required fields"""
        from routes import get_daily_transits
        from models import DailyTransitRequest, BirthData, CurrentLocation, HoroscopePeriod
        
        birth_data = BirthData(
            birth_date="1990-01-01",
            birth_time="12:00",
            latitude=40.7128,
            longitude=-74.0060
        )
        current_location = CurrentLocation(
            latitude=40.7128,
            longitude=-74.0060
        )
        request = DailyTransitRequest(
            birth_data=birth_data,
            current_location=current_location,
            target_date="2024-01-01T00:00:00",
            period=HoroscopePeriod.day
        )
        
        invalid_user = {
            'email': 'test@example.com',
            'name': 'Test User'
        }
        
        with self.assertRaises(Exception):
            asyncio.run(get_daily_transits(request, invalid_user))

if __name__ == '__main__':
    unittest.main()
