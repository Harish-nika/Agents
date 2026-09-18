"""Geocoding helpers (Open-Meteo) with India trip aliases."""

from __future__ import annotations

from typing import Any

import requests

# Common trip spellings → Open-Meteo-friendly names
_PLACE_ALIASES: dict[str, list[str]] = {
    "bangalore": ["Bengaluru", "Bangalore"],
    "bengaluru": ["Bengaluru"],
    "murudeshwar": ["Murdeshwar", "Murudeshwar", "Murdeshwar Island"],
    "murdeshara": ["Murdeshwar", "Murdeshwar Island"],
    "murdeshwar": ["Murdeshwar", "Murdeshwar Island"],
    "jog falls": ["Jog Falls", "Jog Falls (Gersoppa)", "Gersoppa"],
    "jog": ["Jog Falls (Gersoppa)", "Jog Falls"],
    "gokarna": ["Gokarna"],
}


def _alias_candidates(location: str) -> list[str]:
    key = location.strip().lower()
    names = list(_PLACE_ALIASES.get(key, []))
    if location.strip() not in names:
        names.insert(0, location.strip())
    # Also try key without punctuation
    return list(dict.fromkeys(names))


def _pick_india_hit(results: list[dict[str, Any]], preferred_name: str) -> dict[str, Any] | None:
    if not results:
        return None
    india = [r for r in results if (r.get("country") or "").lower() == "india"]
    pool = india or results
    # Prefer Karnataka when relevant
    karnataka = [r for r in pool if (r.get("admin1") or "") == "Karnataka"]
    if karnataka:
        pool = karnataka
    # Prefer exact-ish name match
    pref = preferred_name.lower()
    for r in pool:
        if (r.get("name") or "").lower() == pref:
            return r
    return pool[0]


def geocode_place(location: str) -> dict[str, Any] | None:
    """Resolve a place name to lat/lon via Open-Meteo geocoding."""
    if not location or not location.strip():
        return None
    last_err: Exception | None = None
    for candidate in _alias_candidates(location):
        try:
            resp = requests.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={
                    "name": candidate,
                    "count": 5,
                    "language": "en",
                    "format": "json",
                },
                timeout=30,
            )
            resp.raise_for_status()
            results = resp.json().get("results") or []
            hit = _pick_india_hit(results, candidate)
            if not hit:
                continue
            return {
                "name": hit.get("name", location.strip()),
                "latitude": float(hit["latitude"]),
                "longitude": float(hit["longitude"]),
                "country": hit.get("country", ""),
                "admin1": hit.get("admin1", ""),
            }
        except Exception as e:
            last_err = e
            continue
    if last_err:
        print(f"geocode_place failed for '{location}': {last_err}")
    return None


def geocode_stops(names: list[str]) -> list[dict[str, Any]]:
    """Geocode an ordered list of stop names; keep slots even on failure."""
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
