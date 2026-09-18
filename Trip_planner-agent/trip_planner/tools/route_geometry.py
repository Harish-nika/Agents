"""OSRM route geometry (free public router)."""

from __future__ import annotations

from typing import Any

import requests

from trip_planner.tools.geocode import geocode_stops


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
    names = [n for n in names if n.strip()]
    if not names:
        return {"status": "error", "message": "No stops provided.", "stops": [], "route": None}

    # Prefer provided coords; fill missing via geocode
    resolved: list[dict[str, Any]] = []
    for s in stops:
        name = (s.get("name") or s.get("label") or "").strip()
        if not name:
            continue
        lat = s.get("lat")
        lon = s.get("lon")
        if lat is not None and lon is not None:
            resolved.append(
                {
                    "name": name,
                    "label": s.get("label") or name,
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
