"""Geocoding helpers (Open-Meteo)."""

from __future__ import annotations

from typing import Any

import requests


def geocode_place(location: str) -> dict[str, Any] | None:
    """Resolve a place name to lat/lon via Open-Meteo geocoding."""
    if not location or not location.strip():
        return None
    resp = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": location.strip(), "count": 1, "language": "en", "format": "json"},
        timeout=30,
    )
    resp.raise_for_status()
    results = resp.json().get("results") or []
    if not results:
        return None
    hit = results[0]
    return {
        "name": hit.get("name", location.strip()),
        "latitude": float(hit["latitude"]),
        "longitude": float(hit["longitude"]),
        "country": hit.get("country", ""),
        "admin1": hit.get("admin1", ""),
    }


def geocode_stops(names: list[str]) -> list[dict[str, Any]]:
    """Geocode an ordered list of stop names; skip failures."""
    out: list[dict[str, Any]] = []
    for name in names:
        geo = geocode_place(name)
        if geo:
            out.append(
                {
                    "name": name,
                    "label": geo["name"],
                    "lat": geo["latitude"],
                    "lon": geo["longitude"],
                    "country": geo.get("country", ""),
                }
            )
        else:
            out.append({"name": name, "label": name, "lat": None, "lon": None})
    return out
