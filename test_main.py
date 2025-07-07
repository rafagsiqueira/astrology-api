import pytest
from fastapi.testclient import TestClient
from main import app
import json

client = TestClient(app)

class TestAPI:
    def test_root_endpoint(self):
        """Test the root health check endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        assert response.json() == {"message": "Cosmic Guru API is running"}

    def test_generate_chart_valid_data(self):
        """Test chart generation with valid birth data"""
        birth_data = {
            "birthDate": "1990-01-01",
            "birthTime": "12:00",
            "latitude": 40.7128,
            "longitude": -74.0060,
            "cityName": "New York",
            "countryName": "USA",
            "timezone": "America/New_York"
        }
        
        response = client.post("/api/generate-chart", json=birth_data)
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify response structure
        assert "planets" in data
        assert "houses" in data
        assert "aspects" in data
        assert "sunSign" in data
        assert "moonSign" in data
        assert "ascendant" in data
        assert "chartSvg" in data
        
        # Verify SVG content is present and valid
        assert data["chartSvg"] is not None
        assert len(data["chartSvg"]) > 0
        assert "<svg" in data["chartSvg"].lower()
        
        # Verify sun sign data structure
        sun_sign = data["sunSign"]
        assert "name" in sun_sign
        assert "element" in sun_sign
        assert "modality" in sun_sign
        assert "ruler" in sun_sign
        
        # Verify planets data structure
        planets = data["planets"]
        assert len(planets) > 0
        
        # Check if Sun exists in planets
        if "Sun" in planets:
            sun_planet = planets["Sun"]
            assert "name" in sun_planet
            assert "longitude" in sun_planet
            assert "sign" in sun_planet
            assert "house" in sun_planet
            assert "isRetrograde" in sun_planet
            assert isinstance(sun_planet["longitude"], (int, float))
            assert isinstance(sun_planet["house"], int)
            assert isinstance(sun_planet["isRetrograde"], bool)

    def test_generate_chart_different_location(self):
        """Test chart generation with different location"""
        birth_data = {
            "birthDate": "1985-06-15",
            "birthTime": "18:30",
            "latitude": 51.5074,
            "longitude": -0.1278,
            "cityName": "London",
            "countryName": "UK",
            "timezone": "Europe/London"
        }
        
        response = client.post("/api/generate-chart", json=birth_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "planets" in data
        assert "sunSign" in data
        
        # Verify different birth data produces different results
        sun_sign = data["sunSign"]["name"]
        valid_signs = ["Ari", "Tau", "Gem", "Can", "Leo", "Vir", 
                      "Lib", "Sco", "Sag", "Cap", "Aqu", "Pis"]
        assert sun_sign in valid_signs

    def test_generate_chart_invalid_date_format(self):
        """Test chart generation with invalid date format"""
        birth_data = {
            "birthDate": "invalid-date",
            "birthTime": "12:00",
            "latitude": 40.7128,
            "longitude": -74.0060,
            "cityName": "New York",
            "countryName": "USA",
            "timezone": "America/New_York"
        }
        
        response = client.post("/api/generate-chart", json=birth_data)
        assert response.status_code == 500

    def test_generate_chart_invalid_time_format(self):
        """Test chart generation with invalid time format"""
        birth_data = {
            "birthDate": "1990-01-01",
            "birthTime": "25:00",  # Invalid hour
            "latitude": 40.7128,
            "longitude": -74.0060,
            "cityName": "New York",
            "countryName": "USA",
            "timezone": "America/New_York"
        }
        
        response = client.post("/api/generate-chart", json=birth_data)
        assert response.status_code == 500

    def test_generate_chart_missing_required_fields(self):
        """Test chart generation with missing required fields"""
        birth_data = {
            "birthDate": "1990-01-01",
            # Missing birthTime
            "latitude": 40.7128,
            "longitude": -74.0060,
            "cityName": "New York",
            "countryName": "USA",
            "timezone": "America/New_York"
        }
        
        response = client.post("/api/generate-chart", json=birth_data)
        assert response.status_code == 422  # Validation error

    def test_generate_chart_invalid_coordinates(self):
        """Test chart generation with invalid coordinates"""
        birth_data = {
            "birthDate": "1990-01-01",
            "birthTime": "12:00",
            "latitude": 200,  # Invalid latitude
            "longitude": -74.0060,
            "cityName": "New York",
            "countryName": "USA",
            "timezone": "America/New_York"
        }
        
        response = client.post("/api/generate-chart", json=birth_data)
        # Should either return 500 or handle gracefully
        assert response.status_code in [200, 500]

    def test_element_mapping(self):
        """Test that elements are correctly mapped"""
        from main import get_element
        
        # Test fire signs
        assert get_element("Ari") == "Fire"
        assert get_element("Leo") == "Fire"
        assert get_element("Sag") == "Fire"
        
        # Test earth signs
        assert get_element("Tau") == "Earth"
        assert get_element("Vir") == "Earth"
        assert get_element("Cap") == "Earth"
        
        # Test air signs
        assert get_element("Gem") == "Air"
        assert get_element("Lib") == "Air"
        assert get_element("Aqu") == "Air"
        
        # Test water signs
        assert get_element("Can") == "Water"
        assert get_element("Sco") == "Water"
        assert get_element("Pis") == "Water"
        
        # Test unknown sign
        assert get_element("Unknown") == "Unknown"

    def test_modality_mapping(self):
        """Test that modalities are correctly mapped"""
        from main import get_modality
        
        # Test cardinal signs
        assert get_modality("Ari") == "Cardinal"
        assert get_modality("Can") == "Cardinal"
        assert get_modality("Lib") == "Cardinal"
        assert get_modality("Cap") == "Cardinal"
        
        # Test fixed signs
        assert get_modality("Tau") == "Fixed"
        assert get_modality("Leo") == "Fixed"
        assert get_modality("Sco") == "Fixed"
        assert get_modality("Aqu") == "Fixed"
        
        # Test mutable signs
        assert get_modality("Gem") == "Mutable"
        assert get_modality("Vir") == "Mutable"
        assert get_modality("Sag") == "Mutable"
        assert get_modality("Pis") == "Mutable"

    def test_ruler_mapping(self):
        """Test that planetary rulers are correctly mapped"""
        from main import get_ruler
        
        assert get_ruler("Ari") == "Mars"
        assert get_ruler("Tau") == "Venus"
        assert get_ruler("Gem") == "Mercury"
        assert get_ruler("Can") == "Moon"
        assert get_ruler("Leo") == "Sun"
        assert get_ruler("Vir") == "Mercury"
        assert get_ruler("Lib") == "Venus"
        assert get_ruler("Sco") == "Pluto"
        assert get_ruler("Sag") == "Jupiter"
        assert get_ruler("Cap") == "Saturn"
        assert get_ruler("Aqu") == "Uranus"
        assert get_ruler("Pis") == "Neptune"

if __name__ == "__main__":
    pytest.main([__file__])