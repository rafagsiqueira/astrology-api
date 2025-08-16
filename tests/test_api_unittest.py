import unittest
from unittest.mock import Mock, patch, AsyncMock
import sys
import asyncio

# Mock semantic_kernel modules before any routes import
sys.modules['semantic_kernel'] = Mock()
sys.modules['semantic_kernel.connectors.ai.anthropic'] = Mock()
sys.modules['semantic_kernel.contents'] = Mock()
sys.modules['semantic_kernel.functions'] = Mock()

class TestAPIEndpoints(unittest.TestCase):
    """Test suite for API endpoint integration - focuses on API-specific logic rather than business logic"""

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
                with patch('routes.parse_chart_response') as mock_parse_response:
                    with patch('routes.get_claude_client') as mock_get_claude:
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
                        
                        from anthropic.types import TextBlock
                        mock_text_block = Mock(spec=TextBlock)
                        mock_text_block.text = '"sun": {"influence": "test", "traits": []}'
                        
                        mock_usage = Mock()
                        mock_usage.input_tokens = 100
                        mock_usage.output_tokens = 50
                        
                        mock_response = Mock()
                        mock_response.content = [mock_text_block]
                        mock_response.usage = mock_usage
                        mock_response.stop_reason = 'end_turn'
                        
                        mock_claude = Mock()
                        mock_claude.messages.create.return_value = mock_response
                        mock_get_claude.return_value = mock_claude
                        
                        from models import ChartAnalysis
                        mock_parsed = Mock(spec=ChartAnalysis)
                        mock_parse_response.return_value = mock_parsed
                        
                        result = asyncio.run(generate_chart_endpoint(birth_data, {'uid': 'test-user'}))
                        
                        mock_generate.assert_called_once_with(birth_data)
                        self.assertEqual(result, mock_chart)
                        self.assertEqual(mock_chart.analysis, mock_parsed)

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
                with patch('routes.parse_chart_response') as mock_parse_response:
                    with patch('routes.get_claude_client') as mock_get_claude:
                        mock_chart = Mock()
                        mock_chart_data = {'planets': {}, 'houses': {}}
                        mock_chart.model_dump.return_value = mock_chart_data
                        mock_generate.return_value = mock_chart
                        mock_build_context.return_value = ("cached_context", "user_context")
                        
                        from anthropic.types import TextBlock
                        mock_text_block = Mock(spec=TextBlock)
                        mock_text_block.text = '"sun": {"influence": "test", "traits": []}'
                        
                        mock_usage = Mock()
                        mock_usage.input_tokens = 100
                        mock_usage.output_tokens = 50
                        
                        mock_response = Mock()
                        mock_response.content = [mock_text_block]
                        mock_response.usage = mock_usage
                        mock_response.stop_reason = 'end_turn'
                        
                        mock_claude = Mock()
                        mock_claude.messages.create.return_value = mock_response
                        mock_get_claude.return_value = mock_claude
                        
                        from models import ChartAnalysis
                        mock_parsed = Mock(spec=ChartAnalysis)
                        mock_parse_response.return_value = mock_parsed
                        
                        result = asyncio.run(generate_chart_endpoint(birth_data, user))
                        
                        mock_generate.assert_called_once_with(birth_data)
                        self.assertEqual(result, mock_chart)
                        self.assertEqual(mock_chart.analysis, mock_parsed)

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
        
        with patch('routes.get_claude_client', return_value=None):
            with self.assertRaises(Exception):
                asyncio.run(analyze_personality(analysis_request, {'uid': 'test'}))
        
        mock_user = {'uid': 'test-user', 'email': 'test@example.com'}
        
        with patch('routes.get_claude_client') as mock_get_claude:
            with patch('contexts.generate_birth_chart') as mock_chart:
                mock_chart_result = Mock()
                mock_chart_result.planets = {}
                mock_chart_result.aspects = []
                mock_chart.return_value = mock_chart_result
                
                from anthropic.types import TextBlock
                mock_text_block = Mock(spec=TextBlock)
                mock_text_block.text = '''"overview": "Test overview",
"personality_traits": {
  "description": "Test personality traits description",
  "key_traits": ["Analytical", "Creative"]
},
"emotional_nature": {
  "description": "Test emotional nature description",
  "emotional_characteristics": ["Sensitive", "Intuitive"]
},
"communication_and_intellect": {
  "description": "Test communication description",
  "communication_strengths": ["Articulate", "Thoughtful"]
},
"relationships_and_love": {
  "description": "Test relationships description",
  "relationship_dynamics": ["Loyal", "Supportive"]
},
"career_and_purpose": {
  "description": "Test career description",
  "career_potential": ["Leadership", "Innovation"]
},
"strengths_and_challenges": {
  "strengths": ["Determination", "Creativity"],
  "challenges": ["Perfectionism", "Overthinking"]
},
"life_path": {
  "overview": "Test life path overview",
  "key_development_areas": ["Self-confidence", "Communication"]
}
}'''
                mock_usage = Mock()
                mock_usage.input_tokens = 100
                mock_usage.output_tokens = 50
                
                mock_response = Mock()
                mock_response.content = [mock_text_block]
                mock_response.usage = mock_usage
                mock_response.stop_reason = 'end_turn'
                
                mock_claude = Mock()
                mock_claude.messages.create.return_value = mock_response
                mock_get_claude.return_value = mock_claude
                
                asyncio.run(analyze_personality(analysis_request, mock_user))
                
                mock_chart.assert_called_once()
                mock_get_claude.assert_called_once()
                mock_claude.messages.create.assert_called_once()

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
        
        with patch('routes.get_claude_client') as mock_get_claude:
            with patch('routes.build_personality_context') as mock_build_context:
                with patch('routes.parse_personality_response') as mock_parse_response:
                    mock_build_context.return_value = ("Mocked system", "Mocked user message")
                    
                    from anthropic.types import TextBlock
                    mock_text_block = Mock(spec=TextBlock)
                    mock_text_block.text = '"overview": "Test analysis overview"'
                    mock_usage = Mock()
                    mock_usage.input_tokens = 100
                    mock_usage.output_tokens = 50
                    
                    mock_response = Mock()
                    mock_response.content = [mock_text_block]
                    mock_response.usage = mock_usage
                    mock_response.stop_reason = 'end_turn'
                    
                    mock_claude = Mock()
                    mock_claude.messages.create.return_value = mock_response
                    mock_get_claude.return_value = mock_claude
                    
                    from models import (
                        PersonalityAnalysis, PersonalityTraitsSection, EmotionalNatureSection,
                        CommunicationIntellectSection, RelationshipsLoveSection, CareerPurposeSection,
                        StrengthsChallengesSection, LifePathSection
                    )
                    mock_analysis = PersonalityAnalysis(
                        overview="Test analysis overview",
                        personality_traits=PersonalityTraitsSection(
                            description="Test personality traits description",
                            key_traits=["Analytical", "Creative", "Empathetic"]
                        ),
                        emotional_nature=EmotionalNatureSection(
                            description="Test emotional nature description",
                            emotional_characteristics=["Sensitive", "Intuitive", "Balanced"]
                        ),
                        communication_and_intellect=CommunicationIntellectSection(
                            description="Test communication description",
                            communication_strengths=["Articulate", "Thoughtful", "Persuasive"]
                        ),
                        relationships_and_love=RelationshipsLoveSection(
                            description="Test relationships description",
                            relationship_dynamics=["Loyal", "Supportive", "Understanding"]
                        ),
                        career_and_purpose=CareerPurposeSection(
                            description="Test career description",
                            career_potential=["Leadership", "Innovation", "Service"]
                        ),
                        strengths_and_challenges=StrengthsChallengesSection(
                            strengths=["Determination", "Creativity", "Empathy"],
                            challenges=["Perfectionism", "Overthinking", "Sensitivity"]
                        ),
                        life_path=LifePathSection(
                            overview="Test life path overview",
                            key_development_areas=["Self-confidence", "Communication", "Balance"]
                        )
                    )
                    mock_parse_response.return_value = mock_analysis
                    
                    result = asyncio.run(analyze_personality(analysis_request, user))
                    
                    self.assertEqual(result, mock_analysis)
                    mock_get_claude.assert_called_once()
                    mock_build_context.assert_called_once_with(analysis_request)
                    mock_claude.messages.create.assert_called_once()
                    mock_parse_response.assert_called_once_with(mock_text_block.text)

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
            with patch('routes.get_claude_client') as mock_get_claude:
                with patch('routes.parse_relationship_response') as mock_parse_response:
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
                                
                                from anthropic.types import TextBlock
                                mock_text_block = Mock(spec=TextBlock)
                                mock_text_block.text = "Mocked Claude response"
                                
                                mock_usage = Mock()
                                mock_usage.input_tokens = 100
                                mock_usage.output_tokens = 50
                                
                                mock_claude_response = Mock()
                                mock_claude_response.content = [mock_text_block]
                                mock_claude_response.usage = mock_usage
                                mock_claude_response.stop_reason = 'end_turn'
                                mock_get_claude.return_value.messages.create.return_value = mock_claude_response
                                
                                mock_parse_response.return_value = RelationshipAnalysis(
                                    score=85,
                                    overview="This is a powerful astrological connection with strong karmic ties.",
                                    compatibility_level="Very High",
                                    destiny_signs="Strong karmic connections present",
                                    relationship_aspects=["Sun conjunction Moon", "Venus trine Mars"],
                                    strengths=["Deep emotional understanding", "Natural compatibility"],
                                    challenges=["Intensity may be overwhelming", "Need to maintain independence"],
                                    areas_for_growth=["Embrace the connection while maintaining individual growth"]
                                )
                                
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
            with patch('routes.get_claude_client') as mock_get_claude:
                with patch('routes.parse_relationship_response') as mock_parse_response:
                    mock_build_context.return_value = ("Mocked system", "Mocked user message")
                    mock_get_claude.return_value = None
                    mock_parse_response.side_effect = Exception("Structured analysis failed")
                    
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
            with patch('routes.get_claude_client') as mock_get_claude:
                with patch('routes.parse_relationship_response') as mock_parse_response:
                    mock_build_context.return_value = ("Mocked system", "Mocked user message")
                    mock_get_claude.return_value = None
                    
                    mock_parse_response.return_value = RelationshipAnalysis(
                        score=60,
                        overview="Analysis temporarily unavailable.",
                        compatibility_level="Moderate",
                        destiny_signs="No significant karmic connections detected",
                        relationship_aspects=["Basic astrological compatibility"],
                        strengths=["Basic compatibility analysis"],
                        challenges=["Communication may require effort"],
                        areas_for_growth=["Focus on understanding each other's perspectives"]
                    )
                    
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
            with patch('routes.get_claude_client') as mock_get_claude:
                with patch('routes.parse_relationship_response') as mock_parse_response:
                    with patch('routes.create_astrological_subject') as mock_create_subject:
                        with patch('routes.RelationshipScoreFactory') as mock_score_factory:
                            with patch('routes.generate_birth_chart') as mock_generate_chart:
                                mock_build_context.return_value = ("Mocked system", "Mocked user message")
                                mock_create_subject.return_value = Mock()
                                mock_score_factory.return_value.get_relationship_score.return_value = Mock(score_value=35, score_description="Low", is_destiny_sign=False, aspects=[])
                                mock_chart = Mock()
                                mock_chart.light_svg = "https://test.com/chart.svg"
                                mock_generate_chart.return_value = mock_chart
                                
                                from anthropic.types import TextBlock
                                mock_text_block = Mock(spec=TextBlock)
                                mock_text_block.text = "Mocked Claude response for low score"
                                
                                mock_usage = Mock()
                                mock_usage.input_tokens = 100
                                mock_usage.output_tokens = 50
                                
                                mock_claude_response = Mock()
                                mock_claude_response.content = [mock_text_block]
                                mock_claude_response.usage = mock_usage
                                mock_claude_response.stop_reason = 'end_turn'
                                mock_get_claude.return_value.messages.create.return_value = mock_claude_response
                                
                                mock_parse_response.return_value = RelationshipAnalysis(
                                    score=35,
                                    overview="This relationship may require significant effort to develop compatibility.",
                                    compatibility_level="Low",
                                    destiny_signs="No significant karmic connections",
                                    relationship_aspects=["Limited harmonious aspects"],
                                    strengths=["Opportunity for growth", "Learning from differences"],
                                    challenges=["Different life approaches", "Communication barriers"],
                                    areas_for_growth=["Focus on building understanding through patient communication"]
                                )
                                
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
            target_date="2024-01-01T00:00:00",
            period=HoroscopePeriod.day
        )
        auth_user = {'uid': 'test-user-123'}
        with patch('routes.get_claude_client') as mock_get_claude:
            with patch('routes.generate_transits') as mock_generate:
                with patch('routes.diff_transits') as mock_diff:
                    from models import DailyTransit, DailyTransitChange, TransitChanges, RetrogradeChanges
                    
                    mock_daily_transit = DailyTransit(
                        date=datetime(2024, 1, 1),
                        aspects=[],
                        retrograding=["Mercury"]
                    )
                    
                    mock_transit_change = DailyTransitChange(
                        date="2024-01-01",
                        aspects=TransitChanges(began=[], ended=[]),
                        retrogrades=RetrogradeChanges(began=["Mercury"], ended=[])
                    )
                    
                    mock_generate.return_value = [mock_daily_transit]
                    mock_diff.return_value = [mock_transit_change]

                    from anthropic.types import TextBlock
                    mock_text_block = Mock(spec=TextBlock)
                    mock_text_block.text = '"daily_messages": [{"title": "Daily Focus", "message": "Today is a good day for reflection.", "period": "day"}]}'

                    mock_usage = Mock()
                    mock_usage.input_tokens = 100
                    mock_usage.output_tokens = 50

                    mock_claude_response = Mock()
                    mock_claude_response.content = [mock_text_block]
                    mock_claude_response.usage = mock_usage
                    mock_claude_response.stop_reason = 'end_turn'
                    mock_get_claude.return_value.messages.create.return_value = mock_claude_response
                    
                    result = asyncio.run(get_daily_transits(request, auth_user))
                    
                    self.assertEqual(result.transits, [mock_daily_transit])
                    self.assertEqual(result.changes, [mock_transit_change])
                    mock_generate.assert_called_once()
                    mock_diff.assert_called_once_with([mock_daily_transit])

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

    def test_get_daily_transits_weekly_period(self):
        """Test daily transits with weekly period"""
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
            period=HoroscopePeriod.week
        )
        auth_user = {'uid': 'test-user-123'}
        with patch('routes.get_claude_client') as mock_get_claude:
            with patch('routes.generate_transits') as mock_generate:
                with patch('routes.diff_transits') as mock_diff:
                    from models import DailyTransit, DailyTransitChange, TransitChanges, RetrogradeChanges
                    
                    mock_transits = []
                    mock_changes = []
                    for i in range(7):
                        mock_transit = DailyTransit(
                            date=datetime(2024, 1, i + 1),
                            aspects=[],
                            retrograding=[]
                        )
                        mock_transits.append(mock_transit)
                        
                        mock_change = DailyTransitChange(
                            date=f"2024-01-0{i+1}",
                            aspects=TransitChanges(began=[], ended=[]),
                            retrogrades=RetrogradeChanges(began=[], ended=[])
                        )
                        mock_changes.append(mock_change)
                    
                    mock_generate.return_value = mock_transits
                    mock_diff.return_value = mock_changes

                    from anthropic.types import TextBlock
                    mock_text_block = Mock(spec=TextBlock)
                    mock_text_block.text = '"daily_messages": [{"title": "Daily Focus", "message": "Today is a good day for reflection.", "period": "day"}]}'

                    mock_usage = Mock()
                    mock_usage.input_tokens = 100
                    mock_usage.output_tokens = 50

                    mock_claude_response = Mock()
                    mock_claude_response.content = [mock_text_block]
                    mock_claude_response.usage = mock_usage
                    mock_claude_response.stop_reason = 'end_turn'
                    mock_get_claude.return_value.messages.create.return_value = mock_claude_response
                    
                    result = asyncio.run(get_daily_transits(request, auth_user))
                    
                    self.assertEqual(len(result.transits), 7)
                    self.assertEqual(len(result.changes), 7)
                    mock_generate.assert_called_once_with(
                        birth_data=birth_data,
                        current_location=current_location,
                        start_date=mock_generate.call_args[1]['start_date'],
                        period=HoroscopePeriod.week
                )

    def test_get_daily_transits_monthly_period(self):
        """Test daily transits with monthly period"""
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
            period=HoroscopePeriod.month
        )
        auth_user = {'uid': 'test-user-123'}
        
        with patch('routes.get_claude_client') as mock_get_claude:
            with patch('routes.generate_transits') as mock_generate:
                with patch('routes.diff_transits') as mock_diff:
                    from models import DailyTransit, DailyTransitChange, TransitChanges, RetrogradeChanges
                    
                    mock_transits = [DailyTransit(
                        date=datetime(2024, 1, i + 1),
                        aspects=[],
                        retrograding=[]
                    ) for i in range(30)]
                    mock_changes = [DailyTransitChange(
                        date=f"2024-01-{i+1:02d}",
                        aspects=TransitChanges(began=[], ended=[]),
                        retrogrades=RetrogradeChanges(began=[], ended=[])
                    ) for i in range(30)]
                    
                    mock_generate.return_value = mock_transits
                    mock_diff.return_value = mock_changes

                    from anthropic.types import TextBlock
                    mock_text_block = Mock(spec=TextBlock)
                    mock_text_block.text = '"daily_messages": [{"title": "Daily Focus", "message": "Today is a good day for reflection.", "period": "day"}]}'

                    mock_usage = Mock()
                    mock_usage.input_tokens = 100
                    mock_usage.output_tokens = 50

                    mock_claude_response = Mock()
                    mock_claude_response.content = [mock_text_block]
                    mock_claude_response.usage = mock_usage
                    mock_claude_response.stop_reason = 'end_turn'
                    mock_get_claude.return_value.messages.create.return_value = mock_claude_response
                    
                    result = asyncio.run(get_daily_transits(request, auth_user))
                    
                    self.assertEqual(len(result.transits), 30)
                    self.assertEqual(len(result.changes), 30)
                    mock_generate.assert_called_once_with(
                        birth_data=birth_data,
                        current_location=current_location,
                        start_date=mock_generate.call_args[1]['start_date'],
                        period=HoroscopePeriod.month
                )

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
            target_date="2024-01-01T00:00:00",
            period=HoroscopePeriod.day
        )
        
        auth_user = {
            'uid': 'test-user-123',
            'email': 'test@example.com',
            'name': 'Test User'
        }
        
        with patch('routes.get_claude_client') as mock_get_claude:
            with patch('routes.generate_transits') as mock_generate:
                with patch('routes.diff_transits') as mock_diff:
                    from models import DailyTransit, DailyTransitChange, TransitChanges, RetrogradeChanges
                    
                    mock_transit = DailyTransit(
                        date=datetime(2024, 1, 1),
                        aspects=[],
                        retrograding=[]
                    )
                    mock_change = DailyTransitChange(
                        date="2024-01-01",
                        aspects=TransitChanges(began=[], ended=[]),
                        retrogrades=RetrogradeChanges(began=[], ended=[])
                    )
                    mock_generate.return_value = [mock_transit]
                    mock_diff.return_value = [mock_change]

                    from anthropic.types import TextBlock
                    mock_text_block = Mock(spec=TextBlock)
                    mock_text_block.text = '"daily_messages": [{"title": "Daily Focus", "message": "Today is a good day for reflection.", "period": "day"}]}'

                    mock_usage = Mock()
                    mock_usage.input_tokens = 100
                    mock_usage.output_tokens = 50

                    mock_claude_response = Mock()
                    mock_claude_response.content = [mock_text_block]
                    mock_claude_response.usage = mock_usage
                    mock_claude_response.stop_reason = 'end_turn'
                    mock_get_claude.return_value.messages.create.return_value = mock_claude_response
                    
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
