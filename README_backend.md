# Cosmic Guru Python Backend

This is the Python backend API for the Cosmic Guru Flutter app, providing cosmiclogical chart generation using the kerykeion library.

## Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the API server:
```bash
python main.py
```

The API will be available at `http://localhost:8000`

## API Endpoints

### GET /
Health check endpoint

### POST /api/generate-chart
Generate an cosmiclogical birth chart from birth data

**Request Body:**
```json
{
  "birthDate": "1990-01-01",
  "birthTime": "12:00",
  "latitude": 40.7128,
  "longitude": -74.0060,
  "cityName": "New York",
  "countryName": "USA",
  "timezone": "America/New_York"
}
```

**Response:**
Returns a complete cosmiclogical chart with planetary positions, houses, aspects, and sign data.

## Features

- Uses kerykeion for accurate cosmiclogical calculations
- FastAPI for high-performance API
- CORS enabled for Flutter app integration
- Comprehensive birth chart data extraction
- Error handling and validation
- Comprehensive unit test suite

## Testing

Run the test suite:
```bash
./run_tests.sh
```

Or manually:
```bash
python -m pytest test_main.py -v
```

### Test Coverage
- ✅ API health check endpoint
- ✅ Valid birth chart generation
- ✅ Different locations and timezones
- ✅ Invalid data handling
- ✅ Sign element/modality/ruler mappings
- ✅ Error scenarios and edge cases