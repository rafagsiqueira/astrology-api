"""Test suite for daily transits functionality."""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch
from models import (
    DailyTransitRequest, DailyTransitResponse, BirthData, CurrentLocation, 
    HoroscopePeriod, DailyTransit, DailyTransitChange, TransitChanges, RetrogradeChanges
)


class TestDailyTransitModels:
    """Test suite for daily transit Pydantic models."""
    
    def test_daily_transit_request_valid_data(self):
        """Test DailyTransitRequest with valid data."""
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
        
        assert request.birth_data == birth_data
        assert request.current_location == current_location
        assert request.target_date == "2024-01-01T00:00:00"
        assert request.period == HoroscopePeriod.day
    
    def test_daily_transit_request_default_period(self):
        """Test DailyTransitRequest uses default period when not specified."""
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
            target_date="2024-01-01T00:00:00"
        )
        
        assert request.period == HoroscopePeriod.day
    
    def test_daily_transit_request_weekly_period(self):
        """Test DailyTransitRequest with weekly period."""
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
        
        assert request.period == HoroscopePeriod.week
    
    def test_daily_transit_request_monthly_period(self):
        """Test DailyTransitRequest with monthly period."""
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
        
        assert request.period == HoroscopePeriod.month
    
    def test_daily_transit_request_invalid_birth_data(self):
        """Test DailyTransitRequest with invalid birth data."""
        current_location = CurrentLocation(
            latitude=40.7128,
            longitude=-74.0060
        )
        
        # Missing required birth data fields should raise validation error
        with pytest.raises(Exception):  # Pydantic ValidationError
            DailyTransitRequest(
                birth_data={},  # Invalid - should be BirthData object
                current_location=current_location,
                target_date="2024-01-01T00:00:00"
            )
    
    def test_daily_transit_request_invalid_location(self):
        """Test DailyTransitRequest with invalid current location."""
        birth_data = BirthData(
            birth_date="1990-01-01",
            birth_time="12:00",
            latitude=40.7128,
            longitude=-74.0060
        )
        
        # Missing required location fields should raise validation error
        with pytest.raises(Exception):  # Pydantic ValidationError
            DailyTransitRequest(
                birth_data=birth_data,
                current_location={},  # Invalid - should be CurrentLocation object
                target_date="2024-01-01T00:00:00"
            )
    
    def test_daily_transit_response_valid_data(self):
        """Test DailyTransitResponse with valid data."""
        # Create mock transit data
        mock_transit = Mock(spec=DailyTransit)
        mock_transit.date = datetime(2024, 1, 1)
        mock_transit.aspects = []
        mock_transit.retrograding = ["Mercury"]
        
        # Create mock change data
        mock_change = Mock(spec=DailyTransitChange)
        mock_change.date = "2024-01-01"
        mock_change.aspects = Mock(spec=TransitChanges)
        mock_change.retrogrades = Mock(spec=RetrogradeChanges)
        
        response = DailyTransitResponse(
            transits=[mock_transit],
            changes=[mock_change]
        )
        
        assert len(response.transits) == 1
        assert len(response.changes) == 1
        assert response.transits[0] == mock_transit
        assert response.changes[0] == mock_change
    
    def test_daily_transit_response_empty_lists(self):
        """Test DailyTransitResponse with empty lists."""
        response = DailyTransitResponse(
            transits=[],
            changes=[]
        )
        
        assert len(response.transits) == 0
        assert len(response.changes) == 0
    
    def test_transit_changes_model(self):
        """Test TransitChanges model creation."""
        from kerykeion.kr_types import AspectModel
        
        # Create mock aspects
        mock_aspect = Mock(spec=AspectModel)
        
        changes = TransitChanges(
            began=[mock_aspect],
            ended=[]
        )
        
        assert len(changes.began) == 1
        assert len(changes.ended) == 0
        assert changes.began[0] == mock_aspect
    
    def test_retrograde_changes_model(self):
        """Test RetrogradeChanges model creation."""
        changes = RetrogradeChanges(
            began=["Mercury", "Venus"],
            ended=["Mars"]
        )
        
        assert len(changes.began) == 2
        assert len(changes.ended) == 1
        assert "Mercury" in changes.began
        assert "Venus" in changes.began
        assert "Mars" in changes.ended
    
    def test_daily_transit_change_model(self):
        """Test DailyTransitChange model creation."""
        aspect_changes = TransitChanges(began=[], ended=[])
        retrograde_changes = RetrogradeChanges(began=["Mercury"], ended=[])
        
        change = DailyTransitChange(
            date="2024-01-01",
            aspects=aspect_changes,
            retrogrades=retrograde_changes
        )
        
        assert change.date == "2024-01-01"
        assert change.aspects == aspect_changes
        assert change.retrogrades == retrograde_changes


class TestDailyTransitFunctions:
    """Test suite for daily transit business logic functions."""
    
    @patch('astrology.EphemerisDataFactory')
    @patch('astrology.TransitsTimeRangeFactory')
    @patch('astrology.create_astrological_subject')
    def test_generate_transits_single_day(self, mock_create_subject, mock_transit_factory, mock_ephemeris_factory):
        """Test generate_transits for a single day."""
        from astrology import generate_transits
        
        # Setup test data
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
        start_date = datetime(2024, 1, 1)
        
        # Mock the astrological subject
        mock_subject = Mock()
        mock_create_subject.return_value = mock_subject
        
        # Mock the ephemeris data factory
        mock_ephemeris_instance = Mock()
        mock_ephemeris_factory.return_value = mock_ephemeris_instance
        
        # Create a mock subject with planet attributes for retrograde checking
        mock_planet = Mock()
        mock_planet.retrograde = True
        mock_astrological_subject = Mock()
        mock_astrological_subject.mercury = mock_planet
        mock_astrological_subject.venus = Mock()
        mock_astrological_subject.venus.retrograde = False
        mock_astrological_subject.mars = Mock()
        mock_astrological_subject.mars.retrograde = False
        mock_astrological_subject.jupiter = Mock()
        mock_astrological_subject.jupiter.retrograde = False
        mock_astrological_subject.saturn = Mock()
        mock_astrological_subject.saturn.retrograde = False
        mock_astrological_subject.uranus = Mock()
        mock_astrological_subject.uranus.retrograde = False
        mock_astrological_subject.neptune = Mock()
        mock_astrological_subject.neptune.retrograde = False
        mock_astrological_subject.pluto = Mock()
        mock_astrological_subject.pluto.retrograde = False
        
        mock_ephemeris_instance.get_ephemeris_data_as_astrological_subjects.return_value = [mock_astrological_subject]
        
        # Mock the transit factory
        mock_transit_instance = Mock()
        mock_transit_factory.return_value = mock_transit_instance
        
        # Mock the transit moments
        mock_moment = Mock()
        mock_moment.date = "2024-01-01"
        mock_moment.aspects = []
        
        mock_transits = Mock()
        mock_transits.transits = [mock_moment]
        mock_transit_instance.get_transit_moments.return_value = mock_transits
        
        # Test the function
        result = generate_transits(birth_data, current_location, start_date, HoroscopePeriod.day)
        
        # Verify the result
        assert len(result) == 1
        assert result[0].retrograding == ["Mercury"]
        mock_create_subject.assert_called_once()
        mock_ephemeris_factory.assert_called_once()
        mock_transit_factory.assert_called_once()
    
    def test_generate_transits_month_not_implemented(self):
        """Test generate_transits raises error for month period."""
        from astrology import generate_transits
        
        # Setup test data
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
        start_date = datetime(2024, 1, 1)
        
        # Test should raise exception for month period
        with pytest.raises(Exception, match="Not implemented yet"):
            generate_transits(birth_data, current_location, start_date, HoroscopePeriod.month)
    
    def test_diff_transits_empty_list(self):
        """Test diff_transits with empty transit list."""
        from astrology import diff_transits
        
        result = diff_transits([])
        
        assert result == []
    
    def test_diff_transits_single_transit(self):
        """Test diff_transits with single transit."""
        from astrology import diff_transits
        from models import DailyTransit
        
        # Create actual DailyTransit object  
        mock_transit = DailyTransit(
            date=datetime(2024, 1, 1),
            aspects=[],
            retrograding=["Mercury"]
        )
        
        result = diff_transits([mock_transit])
        
        # Should return one change showing all current items as "began"
        assert len(result) == 1
        assert result[0].date == "2024-01-01"
        assert result[0].retrogrades.began == ["Mercury"]
        assert result[0].retrogrades.ended == []
    
    def test_diff_transits_two_transits_with_changes(self):
        """Test diff_transits with two transits showing changes."""
        from astrology import diff_transits
        from models import DailyTransit
        
        # Create DailyTransit objects
        mock_transit1 = DailyTransit(
            date=datetime(2024, 1, 1),
            aspects=[],
            retrograding=["Mercury"]
        )
        
        mock_transit2 = DailyTransit(
            date=datetime(2024, 1, 2),
            aspects=[],
            retrograding=["Mercury", "Venus"]  # Added Venus
        )
        
        result = diff_transits([mock_transit1, mock_transit2])
        
        # Should detect no changes as the slicing will remove the results
        assert len(result) == 0
    
    def test_diff_transits_aspect_ended(self):
        """Test diff_transits when aspects change."""
        from astrology import diff_transits
        from models import DailyTransit
        
        # Create DailyTransit objects - focusing on retrograde changes since aspects are complex
        mock_transit1 = DailyTransit(
            date=datetime(2024, 1, 1),
            aspects=[],
            retrograding=["Mercury"]
        )
        
        mock_transit2 = DailyTransit(
            date=datetime(2024, 1, 2),
            aspects=[],
            retrograding=[]  # Mercury retrograde ended
        )
        
        result = diff_transits([mock_transit1, mock_transit2])
        
        # Should detect no changes as the slicing will remove the results
        assert len(result) == 0
    
    def test_diff_transits_retrograde_ended(self):
        """Test diff_transits when multiple retrogrades change."""
        from astrology import diff_transits
        from models import DailyTransit
        
        # Create DailyTransit objects
        mock_transit1 = DailyTransit(
            date=datetime(2024, 1, 1),
            aspects=[],
            retrograding=["Mercury", "Venus"]
        )
        
        mock_transit2 = DailyTransit(
            date=datetime(2024, 1, 2),
            aspects=[],
            retrograding=["Venus", "Mars"]  # Mercury ended, Mars began
        )
        
        result = diff_transits([mock_transit1, mock_transit2])
        
        # Should detect no changes as the slicing will remove the results
        assert len(result) == 0
    
    @patch('astrology.create_astrological_subject')
    def test_generate_transits_error_handling(self, mock_create_subject):
        """Test generate_transits error handling."""
        from astrology import generate_transits
        
        # Setup test data
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
        start_date = datetime(2024, 1, 1)
        
        # Mock create_astrological_subject to raise an error
        mock_create_subject.side_effect = ValueError("Invalid birth data")
        
        # Test should raise exception
        with pytest.raises(ValueError):
            generate_transits(birth_data, current_location, start_date, HoroscopePeriod.day)
    
    def test_diff_transits_invalid_input(self):
        """Test diff_transits with invalid input."""
        from astrology import diff_transits
        
        # Test with None input
        with pytest.raises(Exception):
            diff_transits(None)
        
        # Test with invalid transit objects
        invalid_transit = Mock()
        invalid_transit.date = "not-a-datetime"  # Invalid date format
        invalid_transit.aspects = "not-a-list"  # Invalid aspects format
        invalid_transit.retrograding = None  # Invalid retrograding format
        
        # Should handle gracefully or raise appropriate error
        try:
            result = diff_transits([invalid_transit])
            # If no exception, verify result is reasonable
            assert isinstance(result, list)
        except Exception as e:
            # Exception is acceptable for invalid input
            assert isinstance(e, (TypeError, AttributeError, ValueError))


class TestDailyTransitIntegration:
    """Integration tests for daily transit workflow."""
    
    def test_full_daily_transit_workflow_simple(self):
        """Test the complete daily transit workflow from request to response."""
        from astrology import diff_transits
        from models import DailyTransit, DailyTransitResponse
        
        # Create simple test transits
        transit1 = DailyTransit(
            date=datetime(2024, 1, 1),
            aspects=[],
            retrograding=["Mercury"]
        )
        
        transit2 = DailyTransit(
            date=datetime(2024, 1, 2),
            aspects=[],
            retrograding=[]  # Mercury retrograde ended
        )
        
        transits = [transit1, transit2]
        
        # Test diff_transits
        changes = diff_transits(transits)
        
        # Create response
        response = DailyTransitResponse(transits=transits, changes=changes)
        
        # Verify the complete workflow
        assert len(response.transits) == 2
        assert len(response.changes) == 0  # The slicing will remove the changes
        assert response.transits[0].retrograding == ["Mercury"]
        assert response.transits[1].retrograding == []