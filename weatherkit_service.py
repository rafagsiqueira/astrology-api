"""Utilities for interacting with Apple WeatherKit."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import jwt

from config import (
    WEATHERKIT_KEY_ID,
    WEATHERKIT_KEY_PATH,
    WEATHERKIT_SERVICE_ID,
    WEATHERKIT_TEAM_ID,
    get_logger,
)

logger = get_logger(__name__)

WEATHERKIT_AUDIENCE = "https://weatherkit.apple.com/"
WEATHERKIT_BASE_URL = "https://weatherkit.apple.com/api/v1/weather"
WEATHER_LANGUAGE = "en"

_token_cache: Optional[str] = None
_token_expiration: Optional[datetime] = None
_private_key_cache: Optional[str] = None


class WeatherKitConfigurationError(RuntimeError):
    """Raised when WeatherKit configuration is missing."""


def _load_private_key() -> str:
    """Load the WeatherKit private key contents."""
    global _private_key_cache

    if _private_key_cache:
        return _private_key_cache

    if not WEATHERKIT_KEY_PATH:
        raise WeatherKitConfigurationError("WEATHERKIT_KEY_PATH environment variable is not set.")

    key_path = Path(WEATHERKIT_KEY_PATH)
    if not key_path.exists():
        print(f"DEBUG: {key_path}")
        raise WeatherKitConfigurationError(f"WeatherKit key file not found: {WEATHERKIT_KEY_PATH}")

    _private_key_cache = key_path.read_text()
    return _private_key_cache


def _generate_weatherkit_token() -> str:
    """Generate (or reuse) a WeatherKit JWT signed with the ES256 private key."""
    global _token_cache, _token_expiration

    now = datetime.now(timezone.utc)
    if _token_cache and _token_expiration and now < _token_expiration:
        return _token_cache

    private_key = _load_private_key()

    headers = {
        "kid": WEATHERKIT_KEY_ID,
        "alg": "ES256",
        "id": f"{WEATHERKIT_TEAM_ID}.{WEATHERKIT_SERVICE_ID}"
    }

    payload = {
        "iss": WEATHERKIT_TEAM_ID,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=20)).timestamp()),
        "sub": WEATHERKIT_SERVICE_ID,
    }

    token = jwt.encode(payload, private_key, algorithm="ES256", headers=headers)
    _token_cache = token
    _token_expiration = now + timedelta(minutes=19)
    return token


def _extract_temperature(value: Any) -> Optional[float]:
    """Extract temperature value as Celsius."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        if "value" in value:
            return float(value["value"])
        # Some responses might use 'temperature' as key
        for key in ("temperature", "temperatureMax", "temperatureMin"):
            if key in value and isinstance(value[key], (int, float)):
                return float(value[key])
    return None


def _normalise_forecast_day(day: Dict[str, Any]) -> Dict[str, Any]:
    forecast_start = day.get("forecastStart") or day.get("forecastTime")
    if isinstance(forecast_start, str):
        forecast_date = forecast_start.split("T")[0]
    else:
        forecast_date = None

    daytime_forecast = day.get("daytimeForecast") or {}
    if isinstance(daytime_forecast, dict):
        daytime_summary = daytime_forecast.get("summary")
    else:
        daytime_summary = None

    return {
        "date": forecast_date,
        "condition_code": day.get("conditionCode"),
        "symbol_name": day.get("symbolName"),
        "max_temperature_c": _extract_temperature(day.get("temperatureMax")),
        "min_temperature_c": _extract_temperature(day.get("temperatureMin")),
        "precipitation_chance": day.get("precipitationChance"),
        "forecast_summary": daytime_summary or day.get("summary"),
    }


async def fetch_daily_weather_forecast(
    latitude: float,
    longitude: float,
    *,
    start_date: datetime,
    end_date: datetime,
    language: str = WEATHER_LANGUAGE,
    request_headers: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """Fetch the WeatherKit daily forecast between start_date and end_date (inclusive)."""
    token = _generate_weatherkit_token()

    params = {
        "dataSets": "forecastDaily",
        "dailyStart": start_date.strftime("%Y-%m-%d"),
        "dailyEnd": end_date.strftime("%Y-%m-%d"),
        "temperatureUnit": "celsius",
    }

    url = f"{WEATHERKIT_BASE_URL}/{language}/{latitude}/{longitude}"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    if request_headers:
        headers.update(request_headers)

    async def _make_request(token: str, headers: Dict[str, str]):
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            return response.json()

    try:
        payload = await _make_request(token, headers)
    except WeatherKitConfigurationError:
        raise
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 401:
            logger.warning("WeatherKit token rejected (401). Regenerating token and retrying once.")
            global _token_cache, _token_expiration
            _token_cache = None
            _token_expiration = None
            token = _generate_weatherkit_token()
            new_headers = dict(headers)
            new_headers["Authorization"] = f"Bearer {token}"
            payload = await _make_request(token, new_headers)
        else:
            logger.error("WeatherKit request failed: %s", exc)
            raise
    except httpx.HTTPError as exc:
        logger.error("WeatherKit request failed: %s", exc)
        raise

    daily = (
        payload.get("forecastDaily", {})
        .get("days", [])
    )

    forecasts: List[Dict[str, Any]] = []
    for day in daily:
        try:
            forecasts.append(_normalise_forecast_day(day))
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("Failed to parse WeatherKit day entry: %s", exc)

    return forecasts
