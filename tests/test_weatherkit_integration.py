import os
from datetime import datetime, timedelta, timezone

import pytest

from weatherkit_service import (
    WeatherKitConfigurationError,
    fetch_daily_weather_forecast,
)

RUN_WEATHERKIT_TEST = os.getenv("RUN_WEATHERKIT_TEST") == "1"
REQUIRED_ENV_VARS = [
    "WEATHERKIT_KEY_PATH",
]


def _missing_weatherkit_config() -> list[str]:
    return [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]


@pytest.mark.asyncio
@pytest.mark.skipif(
    not RUN_WEATHERKIT_TEST,
    reason="Set RUN_WEATHERKIT_TEST=1 to run WeatherKit integration tests (requires network access).",
)
async def test_fetch_daily_weather_forecast_live() -> None:
    """Integration test that hits Apple WeatherKit if explicitly enabled."""
    missing_vars = _missing_weatherkit_config()
    if missing_vars:
        pytest.skip(f"Missing WeatherKit config: {', '.join(missing_vars)}")

    latitude = float(os.getenv("WEATHERKIT_TEST_LAT", "37.785834"))
    longitude = float(os.getenv("WEATHERKIT_TEST_LON", "-122.406417"))

    start_date = datetime.now(timezone.utc).date()
    end_date = start_date + timedelta(days=2)

    forecasts = []
    try:
        forecasts = await fetch_daily_weather_forecast(
            latitude=latitude,
            longitude=longitude,
            start_date=datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc),
            end_date=datetime.combine(end_date, datetime.min.time(), tzinfo=timezone.utc),
        )
    except WeatherKitConfigurationError as exc:
        pytest.skip(f"WeatherKit configuration error: {exc}")
    except Exception as err:
        print(f"Other exception occured: {err}")

    assert forecasts, "Expected at least one forecast day from WeatherKit"
    first_day = forecasts[0]
    assert "date" in first_day and first_day["date"], "Forecast should include a date"
    assert "condition_code" in first_day, "Forecast should include a condition code"
