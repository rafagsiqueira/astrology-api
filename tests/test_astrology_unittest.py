import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
import re

from models import BirthData

class TestAstrologyHelpers(unittest.TestCase):
    def test_element_mapping(self):
        """Test that elements are correctly mapped"""
        from astrology import get_element
        
        self.assertEqual(get_element("Ari"), "Fire")
        self.assertEqual(get_element("Leo"), "Fire")
        self.assertEqual(get_element("Sag"), "Fire")
        
        self.assertEqual(get_element("Tau"), "Earth")
        self.assertEqual(get_element("Vir"), "Earth")
        self.assertEqual(get_element("Cap"), "Earth")
        
        self.assertEqual(get_element("Gem"), "Air")
        self.assertEqual(get_element("Lib"), "Air")
        self.assertEqual(get_element("Aqu"), "Air")
        
        self.assertEqual(get_element("Can"), "Water")
        self.assertEqual(get_element("Sco"), "Water")
        self.assertEqual(get_element("Pis"), "Water")
        
        self.assertEqual(get_element("Unknown"), "Unknown")

    def test_modality_mapping(self):
        """Test that modalities are correctly mapped"""
        from astrology import get_modality
        
        self.assertEqual(get_modality("Ari"), "Cardinal")
        self.assertEqual(get_modality("Can"), "Cardinal")
        self.assertEqual(get_modality("Lib"), "Cardinal")
        self.assertEqual(get_modality("Cap"), "Cardinal")
        
        self.assertEqual(get_modality("Tau"), "Fixed")
        self.assertEqual(get_modality("Leo"), "Fixed")
        self.assertEqual(get_modality("Sco"), "Fixed")
        self.assertEqual(get_modality("Aqu"), "Fixed")
        
        self.assertEqual(get_modality("Gem"), "Mutable")
        self.assertEqual(get_modality("Vir"), "Mutable")
        self.assertEqual(get_modality("Sag"), "Mutable")
        self.assertEqual(get_modality("Pis"), "Mutable")

    def test_ruler_mapping(self):
        """Test that planetary rulers are correctly mapped"""
        from astrology import get_ruler
        
        self.assertEqual(get_ruler("Ari"), "Mars")
        self.assertEqual(get_ruler("Tau"), "Venus")
        self.assertEqual(get_ruler("Gem"), "Mercury")
        self.assertEqual(get_ruler("Can"), "Moon")
        self.assertEqual(get_ruler("Leo"), "Sun")
        self.assertEqual(get_ruler("Vir"), "Mercury")
        self.assertEqual(get_ruler("Lib"), "Venus")
        self.assertEqual(get_ruler("Sco"), "Pluto")
        self.assertEqual(get_ruler("Sag"), "Jupiter")
        self.assertEqual(get_ruler("Cap"), "Saturn")
        self.assertEqual(get_ruler("Aqu"), "Uranus")
        self.assertEqual(get_ruler("Pis"), "Neptune")


class TestChartGeneration(unittest.TestCase):
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
        
        self.assertTrue(hasattr(chart, 'planets'))
        self.assertTrue(hasattr(chart, 'houses'))
        self.assertTrue(hasattr(chart, 'sun_sign'))
        self.assertTrue(hasattr(chart, 'moon_sign'))
        self.assertTrue(hasattr(chart, 'ascendant'))
        self.assertTrue(hasattr(chart, 'light_svg'))
        
        sun_sign = chart.sun_sign
        self.assertTrue(hasattr(sun_sign, 'name'))
        self.assertTrue(hasattr(sun_sign, 'element'))
        self.assertTrue(hasattr(sun_sign, 'modality'))
        self.assertTrue(hasattr(sun_sign, 'ruling_planet'))
        
        planets = chart.planets
        self.assertGreater(len(planets), 0)
        
        if "Sun" in planets:
            sun_planet = planets["Sun"]
            self.assertTrue(hasattr(sun_planet, 'name'))
            self.assertTrue(hasattr(sun_planet, 'degree'))
            self.assertTrue(hasattr(sun_planet, 'sign'))
            self.assertTrue(hasattr(sun_planet, 'house'))
            self.assertIsInstance(sun_planet.house, int)
    
    def test_generate_birth_chart_different_locations(self):
        """Test chart generation with different geographic locations"""
        from astrology import generate_birth_chart
        
        ny_data = BirthData(
            birth_date="1990-01-01",
            birth_time="12:00",
            latitude=40.7128,
            longitude=-74.0060
        )
        
        london_data = BirthData(
            birth_date="1990-01-01",
            birth_time="12:00",
            latitude=51.5074,
            longitude=-0.1278
        )
        
        ny_chart = generate_birth_chart(ny_data)
        london_chart = generate_birth_chart(london_data)
        
        ny_houses = ny_chart.houses
        london_houses = london_chart.houses
        
        house_differences = False
        for house_name in ny_houses:
            if house_name in london_houses:
                if (ny_houses[house_name].degree != london_houses[house_name].degree or
                    ny_houses[house_name].sign != london_houses[house_name].sign):
                    house_differences = True
                    break
        
        self.assertTrue(house_differences, "Different locations should produce different house positions")
    
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
        svg_content = chart.light_svg
        
        self.assertTrue(svg_content.startswith('<svg') or svg_content.startswith('<?xml'))
        self.assertIn('<svg', svg_content)
        self.assertIn('</svg>', svg_content)
        self.assertGreater(len(svg_content), 1000)
        
        self.assertNotIn('1990-01-01', svg_content)
        self.assertNotIn('40.7128', svg_content)
        self.assertNotIn('-74.0060', svg_content)
    
    def test_chart_sign_validation(self):
        """Test that chart generates valid astrological signs"""
        from astrology import generate_birth_chart
        
        birth_data = BirthData(
            birth_date="1985-06-15",
            birth_time="12:00",
            latitude=40.7128,
            longitude=-74.0060
        )
        
        chart = generate_birth_chart(birth_data)
        
        valid_signs = ["Ari", "Tau", "Gem", "Can", "Leo", "Vir", 
                      "Lib", "Sco", "Sag", "Cap", "Aqu", "Pis"]
        self.assertIn(chart.sun_sign.name, valid_signs)
        self.assertIn(chart.moon_sign.name, valid_signs)
        self.assertIn(chart.ascendant.name, valid_signs)
        
        valid_elements = ["Fire", "Earth", "Air", "Water"]
        self.assertIn(chart.sun_sign.element, valid_elements)
        
        valid_modalities = ["Cardinal", "Fixed", "Mutable"]
        self.assertIn(chart.sun_sign.modality, valid_modalities)
    
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
        
        output_path = Path(__file__).parent.parent / "test_output_chart.svg"
        
        svg_content = chart.light_svg
        
        svg_content = re.sub(r'width="[^"]*"', 'width="484px"', svg_content)
        svg_content = re.sub(r'height="[^"]*"', 'height="484px"', svg_content)
        svg_content = re.sub(r'viewBox="[^"]*"', 'viewBox="0 0 484 484"', svg_content)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(svg_content)
        
        self.assertTrue(output_path.exists())
        self.assertGreater(output_path.stat().st_size, 1000)
        
        print(f"✅ Chart SVG saved to: {output_path}")
        print(f"📊 Chart details: Sun in {chart.sun_sign.name}, Moon in {chart.moon_sign.name}, Ascendant in {chart.ascendant.name}")

if __name__ == '__main__':
    unittest.main()
