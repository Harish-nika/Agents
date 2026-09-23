"""Free OpenStreetMap Overpass POIs near a trip stop (no API key)."""

from __future__ import annotations

import re
from typing import Any, Literal

import requests

Kind = Literal["places", "food", "lodging"]

_OVERPASS_URLS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)

_USER_AGENT = "TripGuide/1.0 (local free travel agent; contact: local)"
_OVERPASS_TIMEOUT_S = 12

# Nodes-only queries stay fast enough for chat turns
_KIND_FILTERS: dict[Kind, str] = {
    "places": """
      node["tourism"~"attraction|museum|viewpoint"](around:{r},{lat},{lon});
      node["leisure"~"beach|park"](around:{r},{lat},{lon});
      node["historic"](around:{r},{lat},{lon});
      node["amenity"="place_of_worship"](around:{r},{lat},{lon});
    """,
    "food": """
      node["amenity"~"restaurant|cafe|fast_food"](around:{r},{lat},{lon});
    """,
    "lodging": """
      node["tourism"~"hotel|guest_house|hostel"](around:{r},{lat},{lon});
    """,
}

_KIND_ICON = {
    "places": "📍",
    "food": "🍽️",
    "lodging": "🛏️",
}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    from math import asin, cos, radians, sin, sqrt

    r = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    )
    return 2 * r * asin(sqrt(a))


def _element_name(tags: dict[str, Any]) -> str:
    return (
        (tags.get("name") or tags.get("name:en") or tags.get("alt_name") or "")
        .strip()
    )


def _element_coords(el: dict[str, Any]) -> tuple[float, float] | None:
    if "lat" in el and "lon" in el:
        return float(el["lat"]), float(el["lon"])
    center = el.get("center") or {}
    if "lat" in center and "lon" in center:
        return float(center["lat"]), float(center["lon"])
    return None


def _element_kind_label(tags: dict[str, Any], kind: Kind) -> str:
    for key in ("tourism", "leisure", "amenity", "historic"):
        val = tags.get(key)
        if val:
            return str(val).replace("_", " ")
    return kind


def fetch_pois_near(
    lat: float,
    lon: float,
    kind: Kind = "places",
    radius_m: int = 12000,
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Return named POIs near lat/lon from Overpass (free).

    Each item: name, lat, lon, kind, category, osm_url, distance_km
    """
    if kind not in _KIND_FILTERS:
        kind = "places"
    radius_m = max(2000, min(int(radius_m), 15000))
    limit = max(1, min(int(limit), 8))
    filt = _KIND_FILTERS[kind].format(r=radius_m, lat=lat, lon=lon)
    query = f"""
    [out:json][timeout:10];
    (
      {filt}
    );
    out body {limit * 2};
    """
    data: dict[str, Any] | None = None
    last_err: Exception | None = None
    for url in _OVERPASS_URLS:
        try:
            resp = requests.post(
                url,
                data={"data": query},
                headers={"User-Agent": _USER_AGENT},
                timeout=_OVERPASS_TIMEOUT_S,
            )
            if resp.status_code >= 400:
                last_err = RuntimeError(f"HTTP {resp.status_code} from {url}")
                continue
            data = resp.json()
            break
        except Exception as e:
            last_err = e
            # Don't burn another 40s on the mirror after a read timeout
            if "timed out" in str(e).lower() or "timeout" in str(e).lower():
                break
            continue
    if data is None:
        if last_err:
            print(f"osm_pois Overpass failed: {last_err}")
        return []

    elements = data.get("elements") or []
    scored: list[tuple[float, dict[str, Any]]] = []
    seen: set[str] = set()
    for el in elements:
        tags = el.get("tags") or {}
        name = _element_name(tags)
        if not name or len(name) < 2:
            continue
        coords = _element_coords(el)
        if not coords:
            continue
        plat, plon = coords
        key = f"{name.lower()}|{round(plat, 4)}|{round(plon, 4)}"
        if key in seen:
            continue
        seen.add(key)
        dist = _haversine_km(lat, lon, plat, plon)
        osm_type = el.get("type") or "node"
        osm_id = el.get("id")
        osm_url = (
            f"https://www.openstreetmap.org/{osm_type}/{osm_id}"
            if osm_id
            else "https://www.openstreetmap.org"
        )
        scored.append(
            (
                dist,
                {
                    "name": name,
                    "lat": plat,
                    "lon": plon,
                    "kind": kind,
                    "category": _element_kind_label(tags, kind),
                    "osm_url": osm_url,
                    "distance_km": round(dist, 2),
                    "icon": _KIND_ICON.get(kind, "📍"),
                },
            )
        )
    scored.sort(key=lambda x: x[0])
    return [item for _, item in scored[:limit]]


def _corridor_samples(
    geos: list[dict[str, Any]], max_samples: int = 4
) -> list[tuple[float, float, str]]:
    """Interleave stops and midpoints so 'on the way' probes are included."""
    if not geos:
        return []
    samples: list[tuple[float, float, str]] = []
    # Always include first stop
    g0 = geos[0]
    samples.append(
        (float(g0["latitude"]), float(g0["longitude"]), str(g0.get("name") or "stop"))
    )
    for i in range(len(geos) - 1):
        if len(samples) >= max_samples:
            break
        a, b = geos[i], geos[i + 1]
        mid_lat = (float(a["latitude"]) + float(b["latitude"])) / 2
        mid_lon = (float(a["longitude"]) + float(b["longitude"])) / 2
        samples.append(
            (
                mid_lat,
                mid_lon,
                f"between {a.get('name') or 'A'} and {b.get('name') or 'B'}",
            )
        )
        if len(samples) >= max_samples:
            break
        # Destination of this leg
        samples.append(
            (float(b["latitude"]), float(b["longitude"]), str(b.get("name") or "stop"))
        )
    # If only one hub, keep just that
    return samples[:max_samples]


def fetch_pois_along_stops(
    stop_names: list[str],
    kind: Kind = "places",
    limit_total: int = 10,
    max_samples: int = 4,
) -> list[dict[str, Any]]:
    """OSM POIs at stops and midpoints along a multi-stop drive corridor."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from trip_planner.tools.geocode import geocode_place

    geos: list[dict[str, Any]] = []
    for name in (stop_names or [])[:4]:
        try:
            geo = geocode_place(name)
        except Exception as e:
            print(f"along-route geocode skip {name}: {e}")
            continue
        if geo and geo.get("latitude") is not None:
            geos.append(geo)
    if not geos:
        return []

    samples = _corridor_samples(geos, max_samples=max_samples)
    per_sample = max(2, min(5, (limit_total + len(samples) - 1) // len(samples)))
    # Midpoints use a wider radius so "on the way" towns show up
    results: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _one(lat: float, lon: float, near: str) -> list[dict[str, Any]]:
        is_mid = near.lower().startswith("between ")
        radius = 15000 if is_mid else (10000 if kind == "places" else 8000)
        batch = fetch_pois_near(lat, lon, kind=kind, radius_m=radius, limit=per_sample)
        out = []
        for p in batch:
            out.append(
                {
                    **p,
                    "near": near,
                    "along_route": True,
                    "on_the_way": is_mid,
                }
            )
        return out

    with ThreadPoolExecutor(max_workers=min(4, len(samples))) as pool:
        futs = {
            pool.submit(_one, lat, lon, near): near for lat, lon, near in samples
        }
        for fut in as_completed(futs):
            try:
                batch = fut.result()
            except Exception as e:
                print(f"along-route OSM skip: {e}")
                continue
            for p in batch:
                key = f"{p['name'].lower()}|{round(p['lat'], 4)}"
                if key in seen:
                    continue
                seen.add(key)
                results.append(p)

    # Prefer on-the-way midpoints, then closer to sample
    results.sort(
        key=lambda p: (0 if p.get("on_the_way") else 1, p.get("distance_km") or 99)
    )
    return results[:limit_total]


_CITY_HINT = re.compile(
    r"\b(in|near|around|at|for)\s+([A-Za-z][A-Za-z\s.'-]{1,40})(?:\s|$|,|\.|:)",
    re.I,
)

# Known hubs to pull from free-text requests
_KNOWN_HUBS = (
    "gokarna",
    "dandeli",
    "murudeshwar",
    "murdeshwar",
    "bengaluru",
    "bangalore",
    "jog falls",
    "mysore",
    "mysuru",
    "mangalore",
    "mangaluru",
    "goa",
    "udupi",
    "hampi",
)


def guess_location_from_request(request: str) -> str | None:
    """Best-effort destination string for geocoding from a specialist request."""
    text = (request or "").strip()
    if not text:
        return None
    lower = text.lower()
    for hub in _KNOWN_HUBS:
        if hub in lower:
            return hub.title() if hub != "jog falls" else "Jog Falls"
    m = _CITY_HINT.search(text)
    if m:
        return m.group(2).strip(" .,;:")
    # Last resort: first Capitalized token run
    m2 = re.search(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b", text)
    if m2:
        return m2.group(1)
    return None
