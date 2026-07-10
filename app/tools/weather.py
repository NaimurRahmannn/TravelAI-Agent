import httpx
from langchain.tools import tool


GEOCODING_URL = (
    "https://geocoding-api.open-meteo.com/v1/search"
)

WEATHER_URL = (
    "https://api.open-meteo.com/v1/forecast"
)


@tool
def get_current_weather(destination: str) -> dict:
    """Get the current weather for a travel destination."""

    geocoding_response = httpx.get(
        GEOCODING_URL,
        params={
            "name": destination,
            "count": 1,
        },
        timeout=10,
    )

    geocoding_response.raise_for_status()

    geocoding_data = geocoding_response.json()

    results = geocoding_data.get("results")

    if not results:
        return {
            "error": (
                f"Could not find destination: "
                f"{destination}"
            )
        }

    location = results[0]

    weather_response = httpx.get(
        WEATHER_URL,
        params={
            "latitude": location["latitude"],
            "longitude": location["longitude"],
            "current": [
                "temperature_2m",
                "apparent_temperature",
                "precipitation",
                "weather_code",
                "wind_speed_10m",
            ],
            "timezone": "auto",
        },
        timeout=10,
    )

    weather_response.raise_for_status()

    weather_data = weather_response.json()

    return {
        "destination": location["name"],
        "country": location.get("country"),
        "current_weather": weather_data["current"],
        "units": weather_data["current_units"],
    }