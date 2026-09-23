"""Weather tools: NWS live (US) + Open-Meteo date-range forecasts."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import requests

from trip_planner.runtime.cards import add_card
from trip_planner.tools.weather_icons import enrich_day

LOCATION_COORDINATES = {
    "sunnyvale": "37.3688,-122.0363",
    "san francisco": "37.7749,-122.4194",
    "lake tahoe": "39.0968,-120.0324",
}


def get_live_weather_forecast(location: str) -> dict:
    """Gets the current, real-time weather forecast for a specified location in the US.

    Args:
        location: The city name, e.g., "San Francisco".

    Returns:
        A dictionary containing the temperature and a detailed forecast.
    """
    print(f"TOOL CALLED: get_live_weather_forecast(location='{location}')")

    normalized_location = location.lower()
    coords_str = None
    for key, val in LOCATION_COORDINATES.items():
        if key in normalized_location:
            coords_str = val
            break
    if not coords_str:
        return {"status": "error", "message": f"I don't have coordinates for {location}."}

    try:
        points_url = f"https://api.weather.gov/points/{coords_str}"
        headers = {"User-Agent": "TripPlanner ADK Agent"}
        points_response = requests.get(points_url, headers=headers, timeout=30)
        points_response.raise_for_status()
        forecast_url = points_response.json()["properties"]["forecast"]

        forecast_response = requests.get(forecast_url, headers=headers, timeout=30)
        forecast_response.raise_for_status()

        current_period = forecast_response.json()["properties"]["periods"][0]
        result = {
            "status": "success",
            "location": location,
            "temperature": f"{current_period['temperature']}°{current_period['temperatureUnit']}",
            "forecast": current_period["detailedForecast"],
        }
        add_card(
            {
                "type": "weather",
                "title": f"Weather — {location}",
                "summary": f"{result['temperature']}: {result['forecast']}",
                "days": [],
            }
        )
        return result
    except requests.exceptions.RequestException as e:
        return {"status": "error", "message": f"API request failed: {e}"}


def _geocode(location: str) -> dict[str, Any] | None:
    """Resolve a place name to lat/lon via Open-Meteo geocoding."""
    resp = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": location, "count": 1, "language": "en", "format": "json"},
        timeout=30,
    )
    resp.raise_for_status()
    results = resp.json().get("results") or []
    if not results:
        return None
    hit = results[0]
    return {
        "name": hit.get("name", location),
        "latitude": hit["latitude"],
        "longitude": hit["longitude"],
        "country": hit.get("country", ""),
    }


def _parse_date(value: str) -> date:
    return datetime.strptime(value.strip()[:10], "%Y-%m-%d").date()


def _fetch_daily(geo: dict[str, Any], start: date, end: date) -> tuple[list[dict], str]:
    """Fetch daily weather; use archive for past dates, forecast otherwise."""
    today = date.today()
    params = {
        "latitude": geo["latitude"],
        "longitude": geo["longitude"],
        "daily": "weathercode,temperature_2m_max,temperature_2m_min,precipitation_sum",
        "timezone": "auto",
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
    }
    # Archive for fully historical ranges; forecast for near-term / upcoming.
    if end < today:
        url = "https://archive-api.open-meteo.com/v1/archive"
        source = "historical"
    else:
        url = "https://api.open-meteo.com/v1/forecast"
        source = "forecast"

    resp = requests.get(url, params=params, timeout=30)
    if resp.status_code >= 400 and source == "forecast":
        # Far-future or out-of-range: fall back to same calendar days last year.
        def _shift_year(d: date, years: int) -> date:
            try:
                return d.replace(year=d.year + years)
            except ValueError:
                # Feb 29 → Feb 28
                return d.replace(month=2, day=28, year=d.year + years)

        last_start = _shift_year(start, -1)
        last_end = _shift_year(end, -1)
        params["start_date"] = last_start.isoformat()
        params["end_date"] = last_end.isoformat()
        resp = requests.get(
            "https://archive-api.open-meteo.com/v1/archive",
            params=params,
            timeout=30,
        )
        source = f"typical_for_season (based on {last_start.isoformat()}–{last_end.isoformat()})"
    resp.raise_for_status()
    daily = resp.json().get("daily") or {}
    days = []
    dates = daily.get("time") or []
    for i, d in enumerate(dates):
        days.append(
            {
                "date": d,
                "temp_max_c": (daily.get("temperature_2m_max") or [None])[i],
                "temp_min_c": (daily.get("temperature_2m_min") or [None])[i],
                "precipitation_mm": (daily.get("precipitation_sum") or [None])[i],
                "weathercode": (daily.get("weathercode") or [None])[i],
            }
        )
    return days, source


def get_weather_for_dates(location: str, start_date: str, end_date: str) -> dict:
    """Get a daily weather forecast for a location between two dates (YYYY-MM-DD).

    Uses Open-Meteo (worldwide). Prefer this when the user has trip dates.
    Past dates use the archive API; far-future dates fall back to last year's
    same calendar window as a seasonal reference.

    Args:
        location: City or place name, e.g. "San Francisco".
        start_date: Trip start date as YYYY-MM-DD.
        end_date: Trip end date as YYYY-MM-DD.

    Returns:
        Daily highs/lows and weather codes for the date range.
    """
    print(
        f"TOOL CALLED: get_weather_for_dates(location='{location}', "
        f"start_date='{start_date}', end_date='{end_date}')"
    )
    try:
        start = _parse_date(start_date)
        end = _parse_date(end_date)
        if end < start:
            return {"status": "error", "message": "end_date must be on or after start_date."}

        geo = _geocode(location)
        if not geo:
            return {"status": "error", "message": f"Could not geocode location: {location}"}

        days, source = _fetch_daily(geo, start, end)
        days = [enrich_day(d) for d in days]
        summary_bits = []
        for day in days[:5]:
            summary_bits.append(
                f"{day['icon']} {day['date']}: {day['temp_min_c']}–{day['temp_max_c']}°C "
                f"({day['label']})"
            )
        add_card(
            {
                "type": "weather",
                "title": f"Weather — {geo['name']}",
                "subtitle": f"{start.isoformat()} → {end.isoformat()}",
                "summary": " · ".join(summary_bits) if summary_bits else "No daily data returned.",
                "days": days,
                "source": source,
            }
        )
        prose = " · ".join(summary_bits) if summary_bits else "No daily data returned."
        return {
            "status": "success",
            "location": geo["name"],
            "message": (
                f"Weather for {geo['name']} ({start.isoformat()} → {end.isoformat()}, "
                f"{source}): {prose}. "
                "Summarize this briefly for the user in natural language — do not paste JSON."
            ),
            "day_count": len(days),
            "source": source,
        }
    except ValueError:
        return {
            "status": "error",
            "message": "Dates must be YYYY-MM-DD (e.g. 2026-03-20).",
        }
    except requests.exceptions.RequestException as e:
        return {"status": "error", "message": f"Weather API request failed: {e}"}
