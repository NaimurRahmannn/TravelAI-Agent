from urllib.parse import quote

import httpx
from langchain.tools import tool
from pydantic import BaseModel, Field

from app.core.config import settings


GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
COUNTRIES_NOW_URL = "https://countriesnow.space/api/v0.1"
WIKIPEDIA_SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary"
WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"
GEOAPIFY_PLACES_URL = "https://api.geoapify.com/v2/places"
HTTP_HEADERS = {
    "User-Agent": "TravelAI-Agent/1.0 (destination-tool)",
}


LOWER_COST_CURRENCIES = {
    "BDT",
    "IDR",
    "INR",
    "KHR",
    "LKR",
    "NPR",
    "PHP",
    "THB",
    "VND",
}

HIGHER_COST_CURRENCIES = {
    "AUD",
    "CHF",
    "DKK",
    "EUR",
    "GBP",
    "ISK",
    "JPY",
    "NOK",
    "NZD",
    "SEK",
    "SGD",
    "USD",
}


class DestinationInfoInput(BaseModel):
    destination: str = Field(description="City, country, or travel destination")
    include_places: bool = Field(
        default=True,
        description="Include nearby attractions, restaurants, and hotels",
    )
    places_radius_meters: int = Field(
        default=5000,
        gt=0,
        le=50000,
        description="Geoapify search radius in meters",
    )


def build_default_summary(destination: str) -> str:
    return (
        f"{destination} can be planned using live location, country, "
        "encyclopedic, and nearby-place signals."
    )


def fetch_destination_location(destination: str) -> dict | None:
    response = httpx.get(
        GEOCODING_URL,
        params={
            "name": destination,
            "count": 1,
            "language": "en",
            "format": "json",
        },
        headers=HTTP_HEADERS,
        timeout=10,
    )
    response.raise_for_status()

    results = response.json().get("results") or []
    if not results:
        return None

    location = results[0]
    return {
        "name": location["name"],
        "country": location.get("country"),
        "country_code": location.get("country_code"),
        "latitude": location["latitude"],
        "longitude": location["longitude"],
        "timezone": location.get("timezone"),
        "population": location.get("population"),
    }


def fetch_country_basics(country: str | None, country_code: str | None) -> dict | None:
    if not country and not country_code:
        return None

    response = httpx.get(
        f"{COUNTRIES_NOW_URL}/countries/info",
        params={"returns": "currency,flag,dialCode,iso2,iso3"},
        headers=HTTP_HEADERS,
        follow_redirects=True,
        timeout=10,
    )
    response.raise_for_status()

    data = response.json()
    if data.get("error"):
        raise ValueError(data.get("msg") or "CountriesNow request failed")

    countries = data.get("data") or []
    match = find_country_record(countries, country, country_code)
    if not match:
        return None

    return {
        "name": match.get("name"),
        "official_name": match.get("name"),
        "region": None,
        "subregion": None,
        "capital": [],
        "currencies": [
            {
                "code": match.get("currency"),
                "name": None,
                "symbol": None,
            }
        ] if match.get("currency") else [],
        "languages": [],
        "timezones": [],
        "calling_code": format_dial_code(match.get("dialCode")),
        "flag": match.get("flag"),
        "cca2": match.get("iso2"),
        "cca3": match.get("iso3"),
    }


def find_country_record(
    countries: list[dict],
    country: str | None,
    country_code: str | None,
) -> dict | None:
    normalized_country = country.strip().lower() if country else None
    normalized_code = country_code.strip().lower() if country_code else None

    for item in countries:
        names = {
            str(item.get("name", "")).lower(),
            str(item.get("iso2", "")).lower(),
            str(item.get("iso3", "")).lower(),
        }

        if normalized_code and normalized_code in names:
            return item

        if normalized_country and normalized_country in names:
            return item

    return None


def format_dial_code(value: str | None) -> str | None:
    if not value:
        return None

    value = str(value).strip()
    if value.startswith("+"):
        return value

    return f"+{value}"


def fetch_wikipedia_summary(destination: str) -> dict | None:
    try:
        response = httpx.get(
            f"{WIKIPEDIA_SUMMARY_URL}/{quote(destination)}",
            headers=HTTP_HEADERS,
            follow_redirects=True,
            timeout=10,
        )

        if response.status_code == 404:
            return None

        response.raise_for_status()
        data = response.json()

        if data.get("type") == "disambiguation":
            return None

        return {
            "title": data.get("title"),
            "description": data.get("description"),
            "summary": data.get("extract"),
            "url": (
                data.get("content_urls", {})
                .get("desktop", {})
                .get("page")
            ),
        }
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 403:
            raise

    return fetch_wikipedia_query_summary(destination)


def fetch_wikipedia_query_summary(destination: str) -> dict | None:
    response = httpx.get(
        WIKIPEDIA_API_URL,
        params={
            "action": "query",
            "format": "json",
            "prop": "extracts|description|info",
            "exintro": 1,
            "explaintext": 1,
            "inprop": "url",
            "redirects": 1,
            "titles": destination,
        },
        headers=HTTP_HEADERS,
        follow_redirects=True,
        timeout=10,
    )
    response.raise_for_status()

    pages = response.json().get("query", {}).get("pages", {})
    if not pages:
        return None

    page = next(iter(pages.values()))
    if "missing" in page:
        return None

    return {
        "title": page.get("title"),
        "description": page.get("description"),
        "summary": page.get("extract"),
        "url": page.get("fullurl"),
    }


def fetch_geoapify_places(
    latitude: float,
    longitude: float,
    radius_meters: int,
) -> dict:
    if not settings.geoapify_api_key:
        return {
            "provider": "geoapify",
            "api_used": False,
            "status": "credentials_missing",
        }

    categories = {
        "attractions": "tourism.sights,tourism.attraction",
        "restaurants": "catering.restaurant",
        "hotels": "accommodation.hotel",
    }
    places = {}

    for label, category_filter in categories.items():
        response = httpx.get(
            GEOAPIFY_PLACES_URL,
            params={
                "categories": category_filter,
                "filter": (
                    f"circle:{longitude},{latitude},{radius_meters}"
                ),
                "bias": f"proximity:{longitude},{latitude}",
                "limit": 5,
                "apiKey": settings.geoapify_api_key,
            },
            headers=HTTP_HEADERS,
            timeout=10,
        )
        response.raise_for_status()

        places[label] = [
            format_geoapify_feature(feature)
            for feature in response.json().get("features", [])
        ]

    return {
        "provider": "geoapify",
        "api_used": True,
        "status": "used",
        **places,
    }


def format_geoapify_feature(feature: dict) -> dict:
    properties = feature.get("properties") or {}
    return {
        "name": properties.get("name"),
        "address": properties.get("formatted"),
        "categories": properties.get("categories", []),
        "distance_meters": properties.get("distance"),
    }


def infer_destination_insights(result: dict) -> dict:
    location = result.get("location") or {}
    country = result.get("country") or {}
    wikipedia = result.get("wikipedia") or {}
    places = result.get("places") or {}
    summary_text = " ".join(
        str(value or "")
        for value in (
            wikipedia.get("summary"),
            wikipedia.get("description"),
            result.get("summary"),
        )
    ).lower()
    place_terms = collect_place_terms(places)

    return {
        "summary": wikipedia.get("summary") or result["summary"],
        "best_time_to_visit": infer_best_time_to_visit(location),
        "cost_level": infer_cost_level(country),
        "travel_styles": infer_travel_styles(summary_text, place_terms),
        "transport_notes": infer_transport_notes(location, summary_text),
        "planning_confidence": infer_planning_confidence(result),
    }


def collect_place_terms(places: dict) -> set[str]:
    terms = set()

    for group in ("attractions", "restaurants", "hotels"):
        for place in places.get(group, []) or []:
            terms.update(place.get("categories", []) or [])
            if place.get("name"):
                terms.add(str(place["name"]).lower())
            terms.add(group)
            if group == "attractions":
                terms.add("culture")
            if group == "restaurants":
                terms.add("food")

    return terms


def infer_best_time_to_visit(location: dict) -> list[str]:
    latitude = location.get("latitude")

    if latitude is None:
        return ["Check seasonal weather before booking"]

    if abs(latitude) <= 23.5:
        return ["Dry season", "Shoulder months outside peak heat/rain"]

    if latitude > 23.5:
        return ["April-June", "September-November"]

    return ["March-May", "September-November"]


def infer_cost_level(country: dict) -> str:
    currencies = country.get("currencies") or []
    currency_codes = {
        item.get("code")
        for item in currencies
        if item.get("code")
    }

    if currency_codes & LOWER_COST_CURRENCIES:
        return "budget_to_moderate"

    if currency_codes & HIGHER_COST_CURRENCIES:
        return "moderate_to_expensive"

    return "unknown"


def infer_travel_styles(
    summary_text: str,
    place_categories: set[str],
) -> list[str]:
    style_keywords = {
        "culture": {
            "attractions",
            "culture",
            "museum",
            "temple",
            "palace",
            "heritage",
            "historic",
            "tourism",
        },
        "food": {"restaurant", "cuisine", "food", "market", "catering"},
        "nature": {"park", "mountain", "garden", "beach", "nature"},
        "city": {"capital", "city", "hotels", "metropolitan", "urban"},
        "nightlife": {"bar", "nightlife", "club"},
        "shopping": {"mall", "shop", "shopping"},
    }
    combined = " ".join([summary_text, " ".join(place_categories)])
    styles = [
        style
        for style, keywords in style_keywords.items()
        if any(keyword in combined for keyword in keywords)
    ]

    return styles or ["general_travel"]


def infer_transport_notes(location: dict, summary_text: str) -> str:
    population = location.get("population") or 0

    if "metro" in summary_text or "rail" in summary_text:
        return (
            "Prioritize rail or metro corridors and choose accommodation near "
            "a convenient station."
        )

    if population >= 5_000_000:
        return (
            "Expect big-city transfer times. Keep daily plans clustered by "
            "area and allow buffer time between neighborhoods."
        )

    if population >= 500_000:
        return (
            "Use a mix of public transport, taxis, and walkable clusters for "
            "efficient sightseeing."
        )

    return (
        "Confirm local transport frequency in advance and group nearby stops "
        "into the same day."
    )


def infer_planning_confidence(result: dict) -> str:
    live_signals = 0

    if result.get("location"):
        live_signals += 1
    if result.get("country"):
        live_signals += 1
    if result.get("wikipedia"):
        live_signals += 1
    if (result.get("places") or {}).get("api_used"):
        live_signals += 1

    if live_signals >= 3:
        return "high"
    if live_signals == 2:
        return "medium"
    return "low"


def build_destination_info(
    destination: str,
    include_places: bool = True,
    places_radius_meters: int = 5000,
) -> dict:
    result = {
        "destination": destination,
        "summary": build_default_summary(destination),
        "best_time_to_visit": [],
        "cost_level": "unknown",
        "travel_styles": [],
        "transport_notes": None,
        "planning_confidence": "low",
        "location": None,
        "country": None,
        "wikipedia": None,
        "places": {
            "provider": "geoapify",
            "api_used": False,
            "status": "disabled" if not include_places else "not_requested",
        },
        "sources": {
            "derived_insights": True,
            "geocoding": {"provider": "open-meteo", "status": "not_requested"},
            "country": {"provider": "countriesnow", "status": "not_requested"},
            "wikipedia": {"provider": "wikipedia", "status": "not_requested"},
        },
    }

    try:
        location = fetch_destination_location(destination)
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        result["sources"]["geocoding"]["status"] = "error"
        result["sources"]["geocoding"]["error"] = str(exc)
        location = None
    else:
        result["sources"]["geocoding"]["status"] = (
            "used" if location else "not_found"
        )

    if location:
        result["location"] = location
        result["destination"] = location["name"]

    country_name = location.get("country") if location else destination
    country_code = location.get("country_code") if location else None

    try:
        country = fetch_country_basics(country_name, country_code)
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        result["sources"]["country"]["status"] = "error"
        result["sources"]["country"]["error"] = str(exc)
        country = None
    else:
        result["sources"]["country"]["status"] = (
            "used" if country else "not_found"
        )

    if country:
        result["country"] = country

    try:
        wikipedia = fetch_wikipedia_summary(destination)
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        result["sources"]["wikipedia"]["status"] = "error"
        result["sources"]["wikipedia"]["error"] = str(exc)
        wikipedia = None
    else:
        result["sources"]["wikipedia"]["status"] = (
            "used" if wikipedia else "not_found"
        )

    if wikipedia:
        result["wikipedia"] = wikipedia

    if include_places and location:
        try:
            result["places"] = fetch_geoapify_places(
                latitude=location["latitude"],
                longitude=location["longitude"],
                radius_meters=places_radius_meters,
            )
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            result["places"] = {
                "provider": "geoapify",
                "api_used": False,
                "status": "error",
                "error": str(exc),
            }
    elif include_places:
        result["places"] = {
            "provider": "geoapify",
            "api_used": False,
            "status": "missing_location",
        }

    result.update(infer_destination_insights(result))

    return result


@tool(args_schema=DestinationInfoInput)
def get_destination_info(
    destination: str,
    include_places: bool = True,
    places_radius_meters: int = 5000,
) -> dict:
    """Get structured destination, country, summary, and place information."""

    return build_destination_info(
        destination=destination,
        include_places=include_places,
        places_radius_meters=places_radius_meters,
    )
