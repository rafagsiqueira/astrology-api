# Avra Python Backend

This is the Python backend API for the Avra Flutter app, providing astrological chart generation using the kerykeion library.

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
Generate an astrological birth chart from birth data

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
Returns a complete astrological chart with planetary positions, houses, aspects, and sign data.

## Features

- Uses kerykeion for accurate astrological calculations
- FastAPI for high-performance API
- CORS enabled for Flutter app integration
- Comprehensive birth chart data extraction
- Error handling and validation
- Comprehensive unit test suite

## Testing

The project is configured to run unit tests automatically using GitHub Actions. The tests are run on every push and pull request to the `main` branch.

You can also run the tests manually using `pytest`:

```bash
pytest
```

## Deployment

The project is deployed to Google Cloud Run using a GitHub Actions workflow. To trigger the deployment, you need to manually trigger the `Deploy to Google Cloud Run` workflow in the Actions tab of the GitHub repository.