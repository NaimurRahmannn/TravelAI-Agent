"""Maps tool — practical movement and location intelligence.

All functions use Geoapify APIs for:
- Geocoding / reverse geocoding
- Routing (drive, walk, bicycle, transit)
- Nearby-place search (airports, hotels, restaurants, etc.)
- Place clustering for efficient itinerary days
- Travel-time matrix between itinerary stops
- Map bounding-box / center / zoom hints for frontend display
"""

from __future__ import annotations

from math import asin, cos, radians, sin, sqrt
from typing import Literal

import httpx
from langchain.tools import tool
from pydantic import BaseModel, Field

from app.core.config import settings

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GEOAPIFY_GEOCODE_URL = "https://api.geoapify.com/v1/geocode/search"
GEOAPIFY_REVERSE_URL = "https://api.geoapify.com/v1/geocode/reverse"
GEOAPIFY_ROUTING_URL = "https://api.geoapify.com/v1/routing"
GEOAPIFY_PLACES_URL = "https://api.geoapify.com/v2/places"

HTTP_HEADERS = {
    "User-Agent": "TravelAI-Agent/1.0 (maps-tool)",
}

TravelMode = Literal["drive", "walk", "bicycle", "transit"]

# Geoapify place category strings keyed by human-friendly labels.
PLACE_CATEGORIES: dict[str, str] = {
    "airport": "airport",
    "hotel": "accommodation.hotel",
    "hostel": "accommodation.hostel",
    "restaurant": "catering.restaurant",
    "cafe": "catering.cafe",
    "fast_food": "catering.fast_food",
    "attraction": "tourism.sights,tourism.attraction",
    "museum": "entertainment.museum",
    "hospital": "healthcare.hospital",
    "pharmacy": "healthcare.pharmacy",
    "atm": "service.financial.atm",
    "bank": "service.financial.bank",
    "bus_station": "public_transport.bus",
    "train_station": "public_transport.train",
    "subway": "public_transport.subway",
    "supermarket": "commercial.supermarket",
    "shopping_mall": "commercial.shopping_mall",
    "parking": "parking",
    "fuel": "service.vehicle.fuel",
    "ev_charging": "service.vehicle.charging_station",
}

EARTH_RADIUS_KM = 6371.0

# ---------------------------------------------------------------------------
# Pydantic input schemas
# ---------------------------------------------------------------------------


class GeocodeInput(BaseModel):
    place: str = Field(description="Place name, address, or city to geocode")


class ReverseGeocodeInput(BaseModel):
    latitude: float = Field(description="Latitude coordinate")
    longitude: float = Field(description="Longitude coordinate")


class RouteInput(BaseModel):
    origin: str = Field(
        description="Origin place name or 'latitude,longitude'",
    )
    destination: str = Field(
        description="Destination place name or 'latitude,longitude'",
    )
    mode: TravelMode = Field(
        default="drive",
        description="Travel mode: drive, walk, bicycle, or transit",
    )


class NearbySearchInput(BaseModel):
    latitude: float = Field(description="Center latitude")
    longitude: float = Field(description="Center longitude")
    category: str = Field(
        description=(
            "Category keyword. Examples: airport, hotel, restaurant, "
            "attraction, hospital, atm, train_station, cafe, supermarket"
        ),
    )
    radius_meters: int = Field(
        default=5000,
        gt=0,
        le=50000,
        description="Search radius in meters",
    )
    limit: int = Field(
        default=10,
        gt=0,
        le=50,
        description="Maximum number of results",
    )


class ClusterPlacesInput(BaseModel):
    places: list[dict] = Field(
        description=(
            "List of place dicts, each with at least "
            "'name', 'latitude', 'longitude'"
        ),
    )
    max_cluster_radius_km: float = Field(
        default=3.0,
        gt=0,
        description="Maximum radius in km to group places together",
    )


class TravelTimeMatrixInput(BaseModel):
    places: list[dict] = Field(
        description=(
            "List of place dicts with 'name', 'latitude', 'longitude'"
        ),
    )
    mode: TravelMode = Field(
        default="drive",
        description="Travel mode for matrix calculation",
    )


class MapBoundsInput(BaseModel):
    places: list[dict] = Field(
        description=(
            "List of place dicts with 'latitude', 'longitude'"
        ),
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _ensure_api_key() -> str:
    """Return the Geoapify API key or raise."""
    key = settings.geoapify_api_key
    if not key:
        raise ValueError(
            "geoapify_api_key is not configured in .env"
        )
    return key


def _haversine(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """Return the great-circle distance in km between two points."""
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))


def _parse_coords(value: str) -> tuple[float, float] | None:
    """Try to parse 'lat,lon' from a string.  Returns None on failure."""
    parts = value.split(",")
    if len(parts) != 2:
        return None
    try:
        return float(parts[0].strip()), float(parts[1].strip())
    except ValueError:
        return None


def _resolve_to_coords(place_or_coords: str) -> tuple[float, float]:
    """Resolve a place name or 'lat,lon' string to (lat, lon)."""
    coords = _parse_coords(place_or_coords)
    if coords is not None:
        return coords

    result = geocode_place_internal(place_or_coords)
    lat = result.get("latitude")
    lon = result.get("longitude")
    if lat is None or lon is None:
        raise ValueError(
            f"Could not geocode '{place_or_coords}' to coordinates"
        )
    return float(lat), float(lon)


def _format_geoapify_feature(feature: dict) -> dict:
    """Extract useful fields from a GeoJSON feature."""
    props = feature.get("properties") or {}
    geometry = feature.get("geometry") or {}
    coords = geometry.get("coordinates") or [None, None]
    return {
        "name": props.get("name"),
        "address": props.get("formatted"),
        "latitude": props.get("lat") or coords[1],
        "longitude": props.get("lon") or coords[0],
        "categories": props.get("categories", []),
        "distance_meters": props.get("distance"),
        "city": props.get("city"),
        "country": props.get("country"),
        "country_code": props.get("country_code"),
    }


# ---------------------------------------------------------------------------
# Core functions (usable by other tools without LangChain wrapping)
# ---------------------------------------------------------------------------


def geocode_place_internal(place: str) -> dict:
    """Forward-geocode a place name via Geoapify."""
    api_key = _ensure_api_key()
    response = httpx.get(
        GEOAPIFY_GEOCODE_URL,
        params={
            "text": place,
            "limit": 1,
            "format": "json",
            "apiKey": api_key,
        },
        headers=HTTP_HEADERS,
        timeout=10,
    )
    response.raise_for_status()

    results = response.json().get("results") or []
    if not results:
        return {
            "provider": "geoapify",
            "status": "not_found",
            "query": place,
        }

    hit = results[0]
    return {
        "provider": "geoapify",
        "status": "found",
        "query": place,
        "name": hit.get("formatted"),
        "latitude": hit.get("lat"),
        "longitude": hit.get("lon"),
        "city": hit.get("city"),
        "state": hit.get("state"),
        "country": hit.get("country"),
        "country_code": hit.get("country_code"),
        "postcode": hit.get("postcode"),
        "result_type": hit.get("result_type"),
    }


def reverse_geocode_internal(
    latitude: float,
    longitude: float,
) -> dict:
    """Reverse-geocode coordinates via Geoapify."""
    api_key = _ensure_api_key()
    response = httpx.get(
        GEOAPIFY_REVERSE_URL,
        params={
            "lat": latitude,
            "lon": longitude,
            "format": "json",
            "apiKey": api_key,
        },
        headers=HTTP_HEADERS,
        timeout=10,
    )
    response.raise_for_status()

    results = response.json().get("results") or []
    if not results:
        return {
            "provider": "geoapify",
            "status": "not_found",
            "latitude": latitude,
            "longitude": longitude,
        }

    hit = results[0]
    return {
        "provider": "geoapify",
        "status": "found",
        "latitude": latitude,
        "longitude": longitude,
        "address": hit.get("formatted"),
        "city": hit.get("city"),
        "state": hit.get("state"),
        "country": hit.get("country"),
        "country_code": hit.get("country_code"),
        "postcode": hit.get("postcode"),
    }


def get_route_internal(
    origin: str,
    destination: str,
    mode: TravelMode = "drive",
) -> dict:
    """Calculate a route between origin and destination via Geoapify."""
    api_key = _ensure_api_key()

    origin_lat, origin_lon = _resolve_to_coords(origin)
    dest_lat, dest_lon = _resolve_to_coords(destination)

    response = httpx.get(
        GEOAPIFY_ROUTING_URL,
        params={
            "waypoints": (
                f"{origin_lat},{origin_lon}"
                f"|{dest_lat},{dest_lon}"
            ),
            "mode": mode,
            "apiKey": api_key,
        },
        headers=HTTP_HEADERS,
        timeout=15,
    )
    response.raise_for_status()

    data = response.json()
    features = data.get("features") or []
    if not features:
        return {
            "provider": "geoapify",
            "status": "no_route",
            "origin": origin,
            "destination": destination,
            "mode": mode,
        }

    route = features[0]
    props = route.get("properties") or {}

    distance_m = props.get("distance", 0)
    time_s = props.get("time", 0)

    # Also calculate straight-line distance for comparison
    straight_km = round(
        _haversine(origin_lat, origin_lon, dest_lat, dest_lon),
        2,
    )

    return {
        "provider": "geoapify",
        "status": "found",
        "origin": {
            "query": origin,
            "latitude": origin_lat,
            "longitude": origin_lon,
        },
        "destination": {
            "query": destination,
            "latitude": dest_lat,
            "longitude": dest_lon,
        },
        "mode": mode,
        "distance_km": round(distance_m / 1000, 2),
        "distance_miles": round(distance_m / 1609.34, 2),
        "duration_minutes": round(time_s / 60, 1),
        "duration_text": _format_duration(time_s),
        "straight_line_km": straight_km,
    }


def find_nearby_places_internal(
    latitude: float,
    longitude: float,
    category: str,
    radius_meters: int = 5000,
    limit: int = 10,
) -> dict:
    """Search for nearby places of a given category via Geoapify."""
    api_key = _ensure_api_key()

    # Resolve category keyword to Geoapify category string
    geoapify_category = PLACE_CATEGORIES.get(
        category.lower().strip(),
        category,
    )

    response = httpx.get(
        GEOAPIFY_PLACES_URL,
        params={
            "categories": geoapify_category,
            "filter": f"circle:{longitude},{latitude},{radius_meters}",
            "bias": f"proximity:{longitude},{latitude}",
            "limit": limit,
            "apiKey": api_key,
        },
        headers=HTTP_HEADERS,
        timeout=10,
    )
    response.raise_for_status()

    features = response.json().get("features") or []
    places = [_format_geoapify_feature(f) for f in features]

    return {
        "provider": "geoapify",
        "status": "found" if places else "no_results",
        "category": category,
        "search_center": {
            "latitude": latitude,
            "longitude": longitude,
        },
        "radius_meters": radius_meters,
        "count": len(places),
        "places": places,
    }


def cluster_places_by_distance(
    places: list[dict],
    max_cluster_radius_km: float = 3.0,
) -> dict:
    """Group places into geographic clusters for efficient itinerary days.

    Uses a simple greedy nearest-neighbour clustering approach:
    1. Start with the first unassigned place as a cluster seed.
    2. Add any remaining unassigned place within *max_cluster_radius_km*
       of the cluster centroid.
    3. Repeat until every place is assigned.
    """
    if not places:
        return {"clusters": [], "count": 0}

    unassigned = list(range(len(places)))
    clusters: list[dict] = []

    while unassigned:
        seed_idx = unassigned.pop(0)
        seed = places[seed_idx]
        cluster_members = [seed]
        center_lat = float(seed["latitude"])
        center_lon = float(seed["longitude"])

        still_unassigned: list[int] = []
        for idx in unassigned:
            candidate = places[idx]
            dist = _haversine(
                center_lat,
                center_lon,
                float(candidate["latitude"]),
                float(candidate["longitude"]),
            )
            if dist <= max_cluster_radius_km:
                cluster_members.append(candidate)
                # Recalculate centroid
                center_lat = sum(
                    float(m["latitude"]) for m in cluster_members
                ) / len(cluster_members)
                center_lon = sum(
                    float(m["longitude"]) for m in cluster_members
                ) / len(cluster_members)
            else:
                still_unassigned.append(idx)

        unassigned = still_unassigned
        clusters.append(
            {
                "cluster_id": len(clusters) + 1,
                "center": {
                    "latitude": round(center_lat, 6),
                    "longitude": round(center_lon, 6),
                },
                "place_count": len(cluster_members),
                "places": [
                    {
                        "name": m.get("name"),
                        "latitude": m.get("latitude"),
                        "longitude": m.get("longitude"),
                    }
                    for m in cluster_members
                ],
            }
        )

    return {
        "clusters": clusters,
        "count": len(clusters),
        "max_cluster_radius_km": max_cluster_radius_km,
        "suggestion": (
            f"You can plan ~{len(clusters)} efficient day(s) by "
            "grouping these stops geographically."
        ),
    }


def compute_travel_time_matrix(
    places: list[dict],
    mode: TravelMode = "drive",
) -> dict:
    """Compute pairwise route distance/time for a list of places.

    For small lists (≤ 8) this calls the routing API for every unique
    pair.  For larger lists it falls back to straight-line estimates to
    avoid excessive API calls.
    """
    n = len(places)
    if n < 2:
        return {
            "status": "need_at_least_2_places",
            "matrix": [],
        }

    use_api = n <= 8
    matrix: list[dict] = []

    for i in range(n):
        for j in range(i + 1, n):
            a = places[i]
            b = places[j]
            lat_a, lon_a = float(a["latitude"]), float(a["longitude"])
            lat_b, lon_b = float(b["latitude"]), float(b["longitude"])

            if use_api:
                try:
                    route = get_route_internal(
                        origin=f"{lat_a},{lon_a}",
                        destination=f"{lat_b},{lon_b}",
                        mode=mode,
                    )
                    matrix.append(
                        {
                            "from": a.get("name", f"place_{i}"),
                            "to": b.get("name", f"place_{j}"),
                            "distance_km": route.get("distance_km"),
                            "duration_minutes": route.get(
                                "duration_minutes"
                            ),
                            "duration_text": route.get("duration_text"),
                            "mode": mode,
                            "source": "routing_api",
                        }
                    )
                except (
                    httpx.HTTPError,
                    KeyError,
                    TypeError,
                    ValueError,
                ):
                    # Fallback to straight-line
                    dist = _haversine(lat_a, lon_a, lat_b, lon_b)
                    matrix.append(
                        _straight_line_entry(a, b, i, j, dist, mode),
                    )
            else:
                dist = _haversine(lat_a, lon_a, lat_b, lon_b)
                matrix.append(
                    _straight_line_entry(a, b, i, j, dist, mode),
                )

    return {
        "mode": mode,
        "place_count": n,
        "pair_count": len(matrix),
        "source": "routing_api" if use_api else "straight_line_estimate",
        "matrix": matrix,
    }


def compute_map_bounds(places: list[dict]) -> dict:
    """Return bounding box, center, and zoom hints for a set of places."""
    if not places:
        return {"status": "no_places"}

    lats = [float(p["latitude"]) for p in places]
    lons = [float(p["longitude"]) for p in places]

    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)
    center_lat = round((min_lat + max_lat) / 2, 6)
    center_lon = round((min_lon + max_lon) / 2, 6)

    # Rough zoom-level hint based on bounding-box span
    span = max(max_lat - min_lat, max_lon - min_lon)
    if span < 0.01:
        zoom = 16
    elif span < 0.05:
        zoom = 14
    elif span < 0.2:
        zoom = 12
    elif span < 1.0:
        zoom = 10
    elif span < 5.0:
        zoom = 8
    elif span < 20.0:
        zoom = 6
    else:
        zoom = 4

    return {
        "bounding_box": {
            "south_west": {
                "latitude": round(min_lat, 6),
                "longitude": round(min_lon, 6),
            },
            "north_east": {
                "latitude": round(max_lat, 6),
                "longitude": round(max_lon, 6),
            },
        },
        "center": {
            "latitude": center_lat,
            "longitude": center_lon,
        },
        "suggested_zoom": zoom,
        "place_count": len(places),
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _format_duration(seconds: float) -> str:
    """Convert seconds to a human-friendly duration string."""
    total_minutes = int(seconds // 60)
    if total_minutes < 60:
        return f"{total_minutes} min"

    hours = total_minutes // 60
    minutes = total_minutes % 60
    if minutes == 0:
        return f"{hours} hr"
    return f"{hours} hr {minutes} min"


def _straight_line_entry(
    a: dict,
    b: dict,
    i: int,
    j: int,
    dist_km: float,
    mode: TravelMode,
) -> dict:
    """Build a matrix entry from straight-line distance with a rough
    speed estimate for the given mode."""
    speed_kmh: dict[str, float] = {
        "drive": 40.0,
        "walk": 5.0,
        "bicycle": 15.0,
        "transit": 25.0,
    }
    est_minutes = round(dist_km / speed_kmh.get(mode, 40.0) * 60, 1)
    return {
        "from": a.get("name", f"place_{i}"),
        "to": b.get("name", f"place_{j}"),
        "distance_km": round(dist_km, 2),
        "duration_minutes": est_minutes,
        "duration_text": _format_duration(est_minutes * 60),
        "mode": mode,
        "source": "straight_line_estimate",
    }


# ---------------------------------------------------------------------------
# LangChain @tool wrappers
# ---------------------------------------------------------------------------


@tool(args_schema=GeocodeInput)
def geocode_place(place: str) -> dict:
    """Convert a place name, address, or city into geographic coordinates."""
    return geocode_place_internal(place)


@tool(args_schema=ReverseGeocodeInput)
def reverse_geocode(latitude: float, longitude: float) -> dict:
    """Convert latitude/longitude coordinates into a readable address."""
    return reverse_geocode_internal(latitude, longitude)


@tool(args_schema=RouteInput)
def get_route(
    origin: str,
    destination: str,
    mode: TravelMode = "drive",
) -> dict:
    """Get route distance, duration, and directions between two places."""
    return get_route_internal(origin, destination, mode)


@tool(args_schema=NearbySearchInput)
def find_nearby_places(
    latitude: float,
    longitude: float,
    category: str,
    radius_meters: int = 5000,
    limit: int = 10,
) -> dict:
    """Find nearby places of a category (airport, hotel, restaurant, etc.)."""
    return find_nearby_places_internal(
        latitude, longitude, category, radius_meters, limit,
    )


@tool(args_schema=ClusterPlacesInput)
def cluster_places(
    places: list[dict],
    max_cluster_radius_km: float = 3.0,
) -> dict:
    """Group itinerary stops into geographic clusters for efficient days."""
    return cluster_places_by_distance(places, max_cluster_radius_km)


@tool(args_schema=TravelTimeMatrixInput)
def travel_time_matrix(
    places: list[dict],
    mode: TravelMode = "drive",
) -> dict:
    """Estimate travel time between every pair of itinerary stops."""
    return compute_travel_time_matrix(places, mode)


@tool(args_schema=MapBoundsInput)
def map_bounds(places: list[dict]) -> dict:
    """Return bounding box, center point, and zoom hint for places."""
    return compute_map_bounds(places)
