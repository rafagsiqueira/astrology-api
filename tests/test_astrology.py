import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from models import BirthData   

class TestCosmiclogyHelpers:
    def test_element_mapping(self):
        """Test that elements are correctly mapped"""
        from astrology import get_element
        
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
        from astrology import get_modality
        
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
        from astrology import get_ruler
        
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


class TestChartGeneration:
    """Test suite for chart generation business logic"""
    
    def test_generate_birth_chart_valid_data(self):
        """Test chart generation with valid birth data"""
        from astrology import generate_birth_chart
        
        birth_data = BirthData(
            birth_date="1990-01-01",
            birth_time="12:00",
            latitude=40.7128,
            longitude=-74.0060
        )
        
        chart = generate_birth_chart(birth_data)
        
        # Verify chart structure
        assert hasattr(chart, 'planets')
        assert hasattr(chart, 'houses')
        # Note: aspects removed from individual charts - only for synastry
        assert hasattr(chart, 'sunSign')
        assert hasattr(chart, 'moonSign')
        assert hasattr(chart, 'ascendant')
        assert hasattr(chart, 'chartSvg')
        
        # Verify sun sign data structure
        sun_sign = chart.sunSign
        assert hasattr(sun_sign, 'name')
        assert hasattr(sun_sign, 'element')
        assert hasattr(sun_sign, 'modality')
        assert hasattr(sun_sign, 'ruling_planet')
        
        # Verify planets data
        planets = chart.planets
        assert len(planets) > 0
        
        # Check if Sun exists in planets
        if "Sun" in planets:
            sun_planet = planets["Sun"]
            assert hasattr(sun_planet, 'name')
            assert hasattr(sun_planet, 'degree')
            assert hasattr(sun_planet, 'sign')
            assert hasattr(sun_planet, 'house')
            assert isinstance(sun_planet.house, int)
    
    def test_generate_birth_chart_different_locations(self):
        """Test chart generation with different geographic locations"""
        from astrology import generate_birth_chart
        
        # Test New York
        ny_data = BirthData(
            birth_date="1990-01-01",
            birth_time="12:00",
            latitude=40.7128,
            longitude=-74.0060
        )
        
        # Test London
        london_data = BirthData(
            birth_date="1990-01-01",
            birth_time="12:00",
            latitude=51.5074,
            longitude=-0.1278
        )
        
        ny_chart = generate_birth_chart(ny_data)
        london_chart = generate_birth_chart(london_data)
        
        # Same birth time but different locations should produce different house positions
        # Check that at least one of the ascendant characteristics differs
        ny_houses = ny_chart.houses
        london_houses = london_chart.houses
        
        # Compare house positions to verify different locations produce different charts
        house_differences = False
        for house_name in ny_houses:
            if house_name in london_houses:
                if (ny_houses[house_name].degree != london_houses[house_name].degree or
                    ny_houses[house_name].sign != london_houses[house_name].sign):
                    house_differences = True
                    break
        
        assert house_differences, "Different locations should produce different house positions"
    
    def test_chart_svg_content_validation(self):
        """Test that generated SVG content is valid"""
        from astrology import generate_birth_chart
        
        birth_data = BirthData(
            birth_date="1990-01-01",
            birth_time="12:00",
            latitude=40.7128,
            longitude=-74.0060
        )
        
        chart = generate_birth_chart(birth_data)
        svg_content = chart.chartSvg
        
        # Basic SVG validation
        assert svg_content.startswith('<svg') or svg_content.startswith('<?xml')
        assert '<svg' in svg_content
        assert '</svg>' in svg_content
        assert len(svg_content) > 1000  # Should be substantial content
        
        # Should not contain personal birth data in text form
        assert '1990-01-01' not in svg_content
        assert '40.7128' not in svg_content
        assert '-74.0060' not in svg_content
    
    def test_chart_sign_validation(self):
        """Test that chart generates valid cosmiclogical signs"""
        from astrology import generate_birth_chart
        
        birth_data = BirthData(
            birth_date="1985-06-15",
            birth_time="12:00",
            latitude=40.7128,
            longitude=-74.0060
        )
        
        chart = generate_birth_chart(birth_data)
        
        # Verify sun sign is valid
        valid_signs = ["Ari", "Tau", "Gem", "Can", "Leo", "Vir", 
                      "Lib", "Sco", "Sag", "Cap", "Aqu", "Pis"]
        assert chart.sunSign.name in valid_signs
        assert chart.moonSign.name in valid_signs
        assert chart.ascendant.name in valid_signs
        
        # Verify elements are valid
        valid_elements = ["Fire", "Earth", "Air", "Water"]
        assert chart.sunSign.element in valid_elements
        
        # Verify modalities are valid
        valid_modalities = ["Cardinal", "Fixed", "Mutable"]
        assert chart.sunSign.modality in valid_modalities
    
    def test_generate_birth_chart_and_save_svg(self):
        """Test chart generation and save SVG for manual inspection"""
        from astrology import generate_birth_chart
        
        birth_data = BirthData(
            birth_date="1986-01-14",
            birth_time="11:35",
            latitude=40.7128,
            longitude=-74.0060
        )
        
        chart = generate_birth_chart(birth_data)
        
        # Save SVG to file for inspection
        output_path = Path(__file__).parent.parent / "test_output_chart.svg"
        
        # Modify SVG to set width, height, and viewport to 550px
        svg_content = chart.chartSvg
        import re
        
        # Replace width and height attributes and viewBox to match manual testing
        svg_content = re.sub(r'width="[^"]*"', 'width="484px"', svg_content)
        svg_content = re.sub(r'height="[^"]*"', 'height="484px"', svg_content)
        svg_content = re.sub(r'viewBox="[^"]*"', 'viewBox="0 0 484 484"', svg_content)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(svg_content)
        
        # Assert that file was created and has content
        assert output_path.exists()
        assert output_path.stat().st_size > 1000  # Should be substantial content
        
        print(f"✅ Chart SVG saved to: {output_path}")
        print(f"📊 Chart details: Sun in {chart.sunSign.name}, Moon in {chart.moonSign.name}, Ascendant in {chart.ascendant.name}")