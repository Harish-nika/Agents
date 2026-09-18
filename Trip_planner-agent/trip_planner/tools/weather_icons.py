"""WMO weathercode → icon/label helpers."""

from __future__ import annotations


def weather_from_code(code: int | None) -> dict[str, str]:
    """Map Open-Meteo WMO weathercode to emoji + short label."""
    if code is None:
        return {"icon": "🌡️", "label": "Weather"}
    c = int(code)
    if c == 0:
        return {"icon": "☀️", "label": "Sunny"}
    if c in (1, 2):
        return {"icon": "🌤️", "label": "Partly cloudy"}
    if c == 3:
        return {"icon": "☁️", "label": "Cloudy"}
    if c in (45, 48):
        return {"icon": "🌫️", "label": "Fog"}
    if c in (51, 53, 55, 56, 57):
        return {"icon": "🌦️", "label": "Drizzle"}
    if c in (61, 63, 65, 66, 67):
        return {"icon": "🌧️", "label": "Rain"}
    if c in (71, 73, 75, 77):
        return {"icon": "🌨️", "label": "Snow"}
    if c in (80, 81, 82):
        return {"icon": "🌧️", "label": "Showers"}
    if c in (85, 86):
        return {"icon": "🌨️", "label": "Snow showers"}
    if c in (95, 96, 99):
        return {"icon": "⛈️", "label": "Thunderstorm"}
    return {"icon": "🌡️", "label": "Mixed"}


def enrich_day(day: dict) -> dict:
    """Add icon/label fields onto a daily forecast dict."""
    meta = weather_from_code(day.get("weathercode"))
    out = dict(day)
    out["icon"] = meta["icon"]
    out["label"] = meta["label"]
    return out
