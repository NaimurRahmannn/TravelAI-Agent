import httpx
from langchain.tools import tool

from app.core.config import settings


GEOCODING_URL = "https://api.geoapify.com/v1/geocode/search"
PLACES_URL = "https://api.geoapify.com/v2/places"


@tool
def find_tourist_attractions(
    destination: str,
    limit: int = 10,
) -> dict:
    """Find real tourist attractions near a travel destination."""

    geocoding_response = httpx.get(
        GEOCODING_URL,
        params={
            "text": destination,
            "limit": 1,
            "apiKey": settings.geoapify_api_key,
        },
        timeout=10,
    )

    geocoding_response.raise_for_status()

    geocoding_data = geocoding_response.json()

    features = geocoding_data.get("features", [])

    if not features:
        return {
            "error": f"Destination not found: {destination}"
        }

    longitude, latitude = features[0]["geometry"]["coordinates"]

    places_response = httpx.get(
        PLACES_URL,
        params={
            "categories": "tourism",
            "filter": (
                f"circle:{longitude},{latitude},10000"
            ),
            "limit": limit,
            "apiKey": settings.geoapify_api_key,
        },
        timeout=10,
    )
    places_response.raise_for_status()

    places_data = places_response.json()

    attractions = []

    for place in places_data.get("features", []):
        properties = place["properties"]

        attractions.append(
            {
                "name": properties.get("name"),
                "address": properties.get("formatted"),
                "categories": properties.get("categories"),
            }
        )

    return {
        "destination": destination,
        "attractions": attractions,
    }