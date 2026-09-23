"""OSRM route geometry (free public router)."""

from __future__ import annotations

import re
from typing import Any

import requests

from trip_planner.tools.geocode import geocode_stops

_SPLIT_STOPS = re.compile(
    r"\s*(?:,|/|;|\||→|->|–|—|\bto\b|\bthen\b)\s*",
    re.IGNORECASE,
)


def _expand_stop_names(names: list[str]) -> list[str]:
    """If a single 'A → B → C' name slipped through, explode it."""
    out: list[str] = []
    seen: set[str] = set()
    for name in names:
        parts = [p.strip(" .") for p in _SPLIT_STOPS.split(name) if p and p.strip(" .")]
        if len(parts) <= 1:
            parts = [name.strip()]
        for p in parts:
            if len(p) < 2:
                continue
            key = p.lower()
            # Keep consecutive duplicates (return legs) but skip immediate dups from noise
            if out and out[-1].lower() == key:
                continue
            # Allow return to origin later; only skip if same as last
            seen.add(key)
            out.append(p)
    return out


def _osrm_route(coords: list[tuple[float, float]]) -> dict[str, Any] | None:
    """coords as (lon, lat) pairs."""
    if len(coords) < 2:
        return None
    path = ";".join(f"{lon},{lat}" for lon, lat in coords)
    url = f"https://router.project-osrm.org/route/v1/driving/{path}"
    resp = requests.get(
        url,
        params={"overview": "full", "geometries": "geojson"},
        timeout=45,
        headers={"User-Agent": "TripGuide/1.0"},
    )
    if resp.status_code >= 400:
        return None
    data = resp.json()
    if data.get("code") != "Ok" or not data.get("routes"):
        return None
    route = data["routes"][0]
    geometry = route.get("geometry") or {}
    # GeoJSON is [lon, lat]; Leaflet wants [lat, lon]
    coords_ll = []
    for pair in geometry.get("coordinates") or []:
        if len(pair) >= 2:
            coords_ll.append([pair[1], pair[0]])
    return {
        "distance_m": route.get("distance"),
        "duration_s": route.get("duration"),
        "coordinates": coords_ll,
    }


def build_trip_geometry(stops: list[dict[str, Any]]) -> dict[str, Any]:
    """Geocode stops (if needed) and return markers + driving polyline.

    Each stop: {name, lat?, lon?}
    """
    names = [s.get("name") or s.get("label") or "" for s in stops]
    names = _expand_stop_names([n for n in names if n.strip()])
    if not names:
        return {"status": "error", "message": "No stops provided.", "stops": [], "route": None}

    # Prefer provided coords; fill missing via geocode
    resolved: list[dict[str, Any]] = []
    coord_by_name = {
        (s.get("name") or s.get("label") or "").strip().lower(): s for s in stops
    }
    for name in names:
        prior = coord_by_name.get(name.lower()) or {}
        lat = prior.get("lat")
        lon = prior.get("lon")
        if lat is not None and lon is not None:
            resolved.append(
                {
                    "name": name,
                    "label": prior.get("label") or name,
                    "lat": float(lat),
                    "lon": float(lon),
                }
            )
        else:
            batch = geocode_stops([name])
            resolved.extend(batch)

    usable = [s for s in resolved if s.get("lat") is not None and s.get("lon") is not None]
    route = None
    if len(usable) >= 2:
        route = _osrm_route([(s["lon"], s["lat"]) for s in usable])

    return {
        "status": "success",
        "stops": resolved,
        "route": route,
    }
