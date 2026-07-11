from datetime import date, datetime, timedelta
from math import ceil
from typing import Literal

import httpx
from langchain.tools import tool
from pydantic import BaseModel, Field

from app.core.config import settings


EXCHANGE_RATE_API_URL = "https://api.frankfurter.dev/v2/rate"
TELEPORT_API_URL = "https://api.teleport.org/api"

BudgetStyle = Literal["budget", "standard", "premium"]

STYLE_MULTIPLIERS: dict[BudgetStyle, dict[str, float]] = {
    "budget": {
        "lodging": 35.0,
        "food": 18.0,
        "transport": 10.0,
        "activities": 12.0,
    },
    "standard": {
        "lodging": 75.0,
        "food": 35.0,
        "transport": 20.0,
        "activities": 25.0,
    },
    "premium": {
        "lodging": 160.0,
        "food": 75.0,
        "transport": 45.0,
        "activities": 60.0,
    },
}


class BudgetEstimateInput(BaseModel):
    destination: str = Field(description="Trip destination")
    duration_days: int = Field(gt=0, description="Number of travel days")
    travelers: int = Field(gt=0, description="Number of travelers")
    style: BudgetStyle = Field(
        default="standard",
        description="Travel spending style",
    )
    currency: str = Field(
        default="USD",
        min_length=3,
        max_length=3,
        description="Three-letter currency code",
    )
    total_budget: float | None = Field(
        default=None,
        gt=0,
        description="Optional budget available for the whole trip",
    )
    use_live_rates: bool = Field(
        default=True,
        description="Use live exchange rates when currency is not USD",
    )
    origin: str | None = Field(
        default=None,
        description="Origin city or IATA code for live flight pricing",
    )
    travel_date: str | None = Field(
        default=None,
        description="Departure date in YYYY-MM-DD format",
    )
    return_date: str | None = Field(
        default=None,
        description="Return date in YYYY-MM-DD format",
    )
    use_live_travel_prices: bool = Field(
        default=False,
        description=(
            "Use optional Amadeus flight and hotel pricing when credentials "
            "are configured"
        ),
    )
    use_free_cost_data: bool = Field(
        default=True,
        description="Use free no-key city cost-of-living data when available",
    )
    use_aviationstack: bool = Field(
        default=True,
        description="Use Aviationstack flight data when API key is configured",
    )


class AmadeusClient:
    def __init__(
        self,
        api_key: str | None = None,
        api_secret: str | None = None,
        base_url: str | None = None,
    ):
        self.api_key = api_key or settings.amadeus_api_key
        self.api_secret = api_secret or settings.amadeus_api_secret
        self.base_url = (base_url or settings.amadeus_base_url).rstrip("/")
        self._access_token: str | None = None

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_secret)

    def _get_access_token(self) -> str:
        if self._access_token:
            return self._access_token

        if not self.is_configured:
            raise ValueError("Amadeus credentials are not configured")

        response = httpx.post(
            f"{self.base_url}/v1/security/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self.api_key,
                "client_secret": self.api_secret,
            },
            timeout=10,
        )
        response.raise_for_status()

        self._access_token = response.json()["access_token"]
        return self._access_token

    def _get(self, path: str, params: dict) -> dict:
        token = self._get_access_token()
        response = httpx.get(
            f"{self.base_url}{path}",
            headers={"Authorization": f"Bearer {token}"},
            params=params,
            timeout=15,
        )
        response.raise_for_status()
        return response.json()

    def resolve_city_code(self, destination: str) -> str:
        destination = destination.strip()

        if len(destination) == 3 and destination.isalpha():
            return destination.upper()

        data = self._get(
            "/v1/reference-data/locations",
            {
                "keyword": destination,
                "subType": "CITY",
                "page[limit]": 1,
            },
        )
        locations = data.get("data") or []

        if not locations:
            raise ValueError(f"No city code found for {destination}")

        city_code = locations[0].get("iataCode")
        if not city_code:
            raise ValueError(f"No IATA city code returned for {destination}")

        return city_code

    def get_lowest_flight_price(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: str | None,
        adults: int,
    ) -> dict | None:
        origin_code = self.resolve_city_code(origin)
        destination_code = self.resolve_city_code(destination)
        params = {
            "originLocationCode": origin_code,
            "destinationLocationCode": destination_code,
            "departureDate": departure_date,
            "adults": adults,
            "currencyCode": "USD",
            "max": 5,
        }

        if return_date:
            params["returnDate"] = return_date

        data = self._get("/v2/shopping/flight-offers", params)
        offers = data.get("data") or []

        if not offers:
            return None

        cheapest = min(
            offers,
            key=lambda offer: float(offer["price"]["total"]),
        )

        return {
            "amount": round(float(cheapest["price"]["total"]), 2),
            "currency": cheapest["price"].get("currency", "USD"),
            "origin": origin_code,
            "destination": destination_code,
            "offer_id": cheapest.get("id"),
        }

    def get_lowest_hotel_price(
        self,
        destination: str,
        check_in_date: str,
        check_out_date: str,
        adults: int,
    ) -> dict | None:
        city_code = self.resolve_city_code(destination)
        hotels_data = self._get(
            "/v1/reference-data/locations/hotels/by-city",
            {
                "cityCode": city_code,
                "radius": 20,
                "radiusUnit": "KM",
            },
        )
        hotel_ids = [
            hotel["hotelId"]
            for hotel in hotels_data.get("data") or []
            if hotel.get("hotelId")
        ][:20]

        if not hotel_ids:
            return None

        params = {
            "hotelIds": ",".join(hotel_ids),
            "checkInDate": check_in_date,
            "checkOutDate": check_out_date,
            "adults": adults,
            "roomQuantity": max(1, ceil(adults / 2)),
            "currency": "USD",
            "bestRateOnly": "true",
        }

        data = self._get("/v3/shopping/hotel-offers", params)
        hotels = data.get("data") or []
        prices = []

        for hotel in hotels:
            for offer in hotel.get("offers") or []:
                price = offer.get("price") or {}
                total = price.get("total")
                if total is None:
                    continue

                prices.append(
                    {
                        "amount": round(float(total), 2),
                        "currency": price.get("currency", "USD"),
                        "hotel_id": hotel.get("hotel", {}).get("hotelId"),
                        "offer_id": offer.get("id"),
                    }
                )

        if not prices:
            return None

        return min(prices, key=lambda price: price["amount"])


class AviationstackClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
    ):
        self.api_key = api_key or settings.aviationstack_api_key
        self.base_url = (
            base_url or settings.aviationstack_base_url
        ).rstrip("/")

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def get_route_flights(
        self,
        origin: str,
        destination: str,
        flight_date: str | None,
        limit: int = 5,
    ) -> dict:
        if not self.is_configured:
            raise ValueError("Aviationstack API key is not configured")

        params = {
            "access_key": self.api_key,
            "dep_iata": origin.upper(),
            "arr_iata": destination.upper(),
            "limit": limit,
        }
        if flight_date:
            params["flight_date"] = flight_date

        response = httpx.get(
            f"{self.base_url}/flights",
            params=params,
            timeout=15,
        )
        response.raise_for_status()

        data = response.json()
        api_error = data.get("error")
        if api_error:
            message = api_error.get("message") or str(api_error)
            raise ValueError(message)

        flights = data.get("data") or []
        return {
            "count": len(flights),
            "sample_flights": [
                {
                    "flight_date": flight.get("flight_date"),
                    "flight_status": flight.get("flight_status"),
                    "airline": (
                        flight.get("airline") or {}
                    ).get("name"),
                    "flight_number": (
                        flight.get("flight") or {}
                    ).get("iata"),
                }
                for flight in flights[:3]
            ],
        }


def fetch_exchange_rate(
    from_currency: str,
    to_currency: str,
) -> float:
    """Fetch a live exchange rate from the configured currency API."""

    from_currency = from_currency.upper()
    to_currency = to_currency.upper()

    if from_currency == to_currency:
        return 1.0

    response = httpx.get(
        f"{EXCHANGE_RATE_API_URL}/{from_currency}/{to_currency}",
        timeout=10,
    )
    response.raise_for_status()

    data = response.json()
    return float(data["rate"])


def fetch_teleport_cost_profile(destination: str) -> dict | None:
    """Fetch free no-key city cost-of-living score data from Teleport."""

    city_response = httpx.get(
        f"{TELEPORT_API_URL}/cities/",
        params={
            "search": destination,
            "limit": 1,
        },
        timeout=10,
    )
    city_response.raise_for_status()

    city_data = city_response.json()
    results = (
        city_data.get("_embedded", {})
        .get("city:search-results", [])
    )

    if not results:
        return None

    city_href = (
        results[0]
        .get("_links", {})
        .get("city:item", {})
        .get("href")
    )
    if not city_href:
        return None

    city_detail_response = httpx.get(city_href, timeout=10)
    city_detail_response.raise_for_status()

    city_detail = city_detail_response.json()
    urban_area_href = (
        city_detail.get("_links", {})
        .get("city:urban_area", {})
        .get("href")
    )
    if not urban_area_href:
        return None

    scores_response = httpx.get(
        f"{urban_area_href.rstrip('/')}/scores/",
        timeout=10,
    )
    scores_response.raise_for_status()

    scores_data = scores_response.json()
    categories = scores_data.get("categories", [])
    cost_score = None

    for category in categories:
        if category.get("name") == "Cost of Living":
            cost_score = float(category["score_out_of_10"])
            break

    if cost_score is None:
        return None

    # Teleport scores are "higher is better"; for budget estimation that means
    # higher affordability should lower the local expense multiplier.
    multiplier = round(max(0.65, min(1.45, 1.45 - (cost_score / 10))), 2)

    return {
        "provider": "teleport",
        "city": results[0].get("matching_full_name", destination),
        "score_out_of_10": round(cost_score, 2),
        "expense_multiplier": multiplier,
    }


def convert_budget_amounts(
    estimate: dict,
    to_currency: str,
    rate: float,
) -> dict:
    """Convert the money fields in a budget estimate."""

    converted = estimate.copy()
    converted["currency"] = to_currency.upper()
    converted["exchange_rate"] = rate
    converted["source_currency"] = estimate["currency"]
    converted["categories"] = {
        name: round(amount * rate, 2)
        for name, amount in estimate["categories"].items()
    }

    for field in (
        "contingency",
        "estimated_total",
        "per_person",
        "per_day",
        "available_budget",
        "difference",
    ):
        if field in converted:
            converted[field] = round(converted[field] * rate, 2)

    return converted


def add_budget_comparison(
    estimate: dict,
    total_budget: float,
) -> dict:
    """Compare an estimate against the available trip budget."""

    compared = estimate.copy()
    difference = round(total_budget - compared["estimated_total"], 2)
    compared["available_budget"] = round(total_budget, 2)
    compared["difference"] = difference
    compared["status"] = (
        "within_budget"
        if difference >= 0
        else "over_budget"
    )
    return compared


def parse_trip_date(value: str | None) -> date | None:
    if not value:
        return None

    return datetime.strptime(value, "%Y-%m-%d").date()


def get_trip_dates(
    travel_date: str | None,
    return_date: str | None,
    duration_days: int,
) -> tuple[str | None, str | None]:
    departure = parse_trip_date(travel_date)

    if departure is None:
        return None, None

    if return_date:
        checkout = parse_trip_date(return_date)
    else:
        checkout = departure + timedelta(days=duration_days)

    if checkout is None:
        return departure.isoformat(), None

    return departure.isoformat(), checkout.isoformat()


def recalculate_budget_totals(
    estimate: dict,
    total_budget: float | None = None,
) -> dict:
    recalculated = estimate.copy()
    subtotal = round(sum(recalculated["categories"].values()), 2)
    contingency = round(subtotal * 0.1, 2)
    estimated_total = round(subtotal + contingency, 2)

    recalculated["contingency"] = contingency
    recalculated["estimated_total"] = estimated_total
    recalculated["per_person"] = round(
        estimated_total / recalculated["travelers"],
        2,
    )
    recalculated["per_day"] = round(
        estimated_total / recalculated["duration_days"],
        2,
    )

    if total_budget is not None:
        recalculated = add_budget_comparison(
            recalculated,
            total_budget,
        )

    return recalculated


def estimate_flight_cost(
    travelers: int,
    style: BudgetStyle,
) -> float:
    per_person_estimates: dict[BudgetStyle, float] = {
        "budget": 250.0,
        "standard": 450.0,
        "premium": 900.0,
    }
    return round(per_person_estimates[style] * travelers, 2)


def apply_aviationstack_flight_data(
    estimate: dict,
    origin: str | None,
    destination: str,
    travel_date: str | None,
) -> dict:
    enriched = estimate.copy()
    enriched["categories"] = estimate["categories"].copy()
    enriched["flight_data"] = {
        "provider": "aviationstack",
        "api_used": False,
    }

    if not origin:
        enriched["flight_data"]["status"] = "missing_origin"
        return enriched

    if len(origin.strip()) != 3 or len(destination.strip()) != 3:
        enriched["flight_data"]["status"] = "requires_iata_codes"
        enriched["flight_data"]["note"] = (
            "Aviationstack route lookup needs 3-letter origin and "
            "destination IATA codes, such as JFK and DAC."
        )
        return enriched

    client = AviationstackClient()
    if not client.is_configured:
        enriched["flight_data"]["status"] = "credentials_missing"
        return enriched

    try:
        route_data = client.get_route_flights(
            origin=origin,
            destination=destination,
            flight_date=travel_date,
        )
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        enriched["flight_data"]["status"] = "error"
        enriched["flight_data"]["error"] = str(exc)
        return enriched

    enriched["flight_data"] = {
        "provider": "aviationstack",
        "api_used": True,
        "status": "used" if route_data["count"] else "no_flights_found",
        **route_data,
        "note": (
            "Aviationstack provides flight data, not ticket fares; "
            "flight budget is estimated."
        ),
    }

    if route_data["count"]:
        enriched["categories"]["flights"] = estimate_flight_cost(
            travelers=estimate["travelers"],
            style=estimate["style"],
        )
        enriched["pricing_source"] = (
            f"{enriched['pricing_source']}_with_aviationstack_flight_data"
        )
        return recalculate_budget_totals(enriched)

    return enriched


def apply_free_cost_of_living_data(
    estimate: dict,
    destination: str,
) -> dict:
    adjusted = estimate.copy()
    adjusted["categories"] = estimate["categories"].copy()

    try:
        cost_profile = fetch_teleport_cost_profile(destination)
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        adjusted["free_cost_data"] = {
            "provider": "teleport",
            "api_used": False,
            "status": "error",
            "error": str(exc),
        }
        return adjusted

    if cost_profile is None:
        adjusted["free_cost_data"] = {
            "provider": "teleport",
            "api_used": False,
            "status": "no_city_cost_data",
        }
        return adjusted

    multiplier = cost_profile["expense_multiplier"]
    adjustable_categories = (
        "lodging",
        "food",
        "transport",
        "activities",
    )

    for category in adjustable_categories:
        if category in adjusted["categories"]:
            adjusted["categories"][category] = round(
                adjusted["categories"][category] * multiplier,
                2,
            )

    adjusted["free_cost_data"] = {
        **cost_profile,
        "api_used": True,
        "status": "used",
    }
    adjusted["pricing_source"] = (
        f"{adjusted['pricing_source']}_adjusted_with_teleport"
    )

    return recalculate_budget_totals(adjusted)


def apply_live_travel_prices(
    estimate: dict,
    destination: str,
    duration_days: int,
    travelers: int,
    origin: str | None,
    travel_date: str | None,
    return_date: str | None,
) -> dict:
    enriched = estimate.copy()
    enriched["categories"] = estimate["categories"].copy()
    enriched["live_pricing"] = {
        "provider": "amadeus",
        "api_used": False,
        "flight": {"status": "skipped"},
        "hotel": {"status": "skipped"},
    }

    client = AmadeusClient()
    if not client.is_configured:
        enriched["live_pricing"]["status"] = "credentials_missing"
        return enriched

    departure, checkout = get_trip_dates(
        travel_date=travel_date,
        return_date=return_date,
        duration_days=duration_days,
    )

    if origin and departure:
        try:
            flight_price = client.get_lowest_flight_price(
                origin=origin,
                destination=destination,
                departure_date=departure,
                return_date=checkout,
                adults=travelers,
            )
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            enriched["live_pricing"]["flight"] = {
                "status": "error",
                "error": str(exc),
            }
        else:
            if flight_price:
                enriched["categories"]["flights"] = flight_price["amount"]
                enriched["live_pricing"]["api_used"] = True
                enriched["live_pricing"]["flight"] = {
                    "status": "used",
                    **flight_price,
                }
            else:
                enriched["live_pricing"]["flight"] = {
                    "status": "no_offers",
                }
    else:
        enriched["live_pricing"]["flight"] = {
            "status": "missing_origin_or_travel_date",
        }

    if departure and checkout:
        try:
            hotel_price = client.get_lowest_hotel_price(
                destination=destination,
                check_in_date=departure,
                check_out_date=checkout,
                adults=travelers,
            )
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            enriched["live_pricing"]["hotel"] = {
                "status": "error",
                "error": str(exc),
            }
        else:
            if hotel_price:
                enriched["categories"]["lodging"] = hotel_price["amount"]
                enriched["live_pricing"]["api_used"] = True
                enriched["live_pricing"]["hotel"] = {
                    "status": "used",
                    **hotel_price,
                }
            else:
                enriched["live_pricing"]["hotel"] = {
                    "status": "no_offers",
                }
    else:
        enriched["live_pricing"]["hotel"] = {
            "status": "missing_travel_date",
        }

    if enriched["live_pricing"]["api_used"]:
        enriched["pricing_source"] = "local_rates_with_live_amadeus_prices"

    return recalculate_budget_totals(enriched)


def build_budget_estimate(
    destination: str,
    duration_days: int,
    travelers: int,
    style: BudgetStyle = "standard",
    total_budget: float | None = None,
) -> dict:
    """Create a deterministic travel budget estimate in USD."""

    if duration_days <= 0:
        raise ValueError("duration_days must be greater than 0")

    if travelers <= 0:
        raise ValueError("travelers must be greater than 0")

    if style not in STYLE_MULTIPLIERS:
        valid_styles = ", ".join(STYLE_MULTIPLIERS)
        raise ValueError(f"style must be one of: {valid_styles}")

    daily_rates = STYLE_MULTIPLIERS[style]

    categories = {
        name: round(rate * duration_days * travelers, 2)
        for name, rate in daily_rates.items()
    }
    subtotal = round(sum(categories.values()), 2)
    contingency = round(subtotal * 0.1, 2)
    estimated_total = round(subtotal + contingency, 2)
    per_person = round(estimated_total / travelers, 2)
    per_day = round(estimated_total / duration_days, 2)

    result = {
        "destination": destination,
        "duration_days": duration_days,
        "travelers": travelers,
        "style": style,
        "currency": "USD",
        "pricing_source": "local_usd_rates",
        "categories": categories,
        "contingency": contingency,
        "estimated_total": estimated_total,
        "per_person": per_person,
        "per_day": per_day,
    }

    if total_budget is not None:
        result = add_budget_comparison(result, total_budget)

    return result


@tool(args_schema=BudgetEstimateInput)
def estimate_travel_budget(
    destination: str,
    duration_days: int,
    travelers: int,
    style: BudgetStyle = "standard",
    currency: str = "USD",
    total_budget: float | None = None,
    use_live_rates: bool = True,
    origin: str | None = None,
    travel_date: str | None = None,
    return_date: str | None = None,
    use_live_travel_prices: bool = False,
    use_free_cost_data: bool = True,
    use_aviationstack: bool = True,
) -> dict:
    """Estimate a travel budget using live travel prices when available."""

    target_currency = currency.upper()
    estimate = build_budget_estimate(
        destination=destination,
        duration_days=duration_days,
        travelers=travelers,
        style=style,
        total_budget=total_budget if target_currency == "USD" else None,
    )

    if use_live_travel_prices:
        estimate = apply_live_travel_prices(
            estimate=estimate,
            destination=destination,
            duration_days=duration_days,
            travelers=travelers,
            origin=origin,
            travel_date=travel_date,
            return_date=return_date,
        )
        if target_currency == "USD" and total_budget is not None:
            estimate = add_budget_comparison(estimate, total_budget)
    else:
        estimate["live_pricing"] = {
            "provider": "free_estimate",
            "api_used": False,
            "status": "no_key_free_mode",
            "note": (
                "No-key live flight and hotel price APIs are not reliable "
                "or generally available. Using local travel estimates."
            ),
        }

    if use_aviationstack:
        estimate = apply_aviationstack_flight_data(
            estimate=estimate,
            origin=origin,
            destination=destination,
            travel_date=travel_date,
        )
        if target_currency == "USD" and total_budget is not None:
            estimate = add_budget_comparison(estimate, total_budget)
    else:
        estimate["flight_data"] = {
            "provider": "aviationstack",
            "api_used": False,
            "status": "disabled",
        }

    if use_free_cost_data:
        estimate = apply_free_cost_of_living_data(
            estimate=estimate,
            destination=destination,
        )
        if target_currency == "USD" and total_budget is not None:
            estimate = add_budget_comparison(estimate, total_budget)
    else:
        estimate["free_cost_data"] = {
            "provider": "teleport",
            "api_used": False,
            "status": "disabled",
        }

    if target_currency == "USD":
        estimate["api_used"] = (
            estimate["live_pricing"]["api_used"]
            or estimate["flight_data"]["api_used"]
            or estimate["free_cost_data"]["api_used"]
        )
        return estimate

    if not use_live_rates:
        estimate["requested_currency"] = target_currency
        estimate["api_used"] = (
            estimate["live_pricing"]["api_used"]
            or estimate["flight_data"]["api_used"]
            or estimate["free_cost_data"]["api_used"]
        )
        estimate["conversion_note"] = (
            "Live exchange rates were disabled; amounts remain in USD."
        )
        return estimate

    try:
        rate = fetch_exchange_rate("USD", target_currency)
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        estimate["requested_currency"] = target_currency
        estimate["api_used"] = (
            estimate["live_pricing"]["api_used"]
            or estimate["flight_data"]["api_used"]
            or estimate["free_cost_data"]["api_used"]
        )
        estimate["conversion_error"] = str(exc)
        estimate["conversion_note"] = (
            "Live exchange rate lookup failed; amounts remain in USD."
        )
        return estimate

    estimate = convert_budget_amounts(
        estimate=estimate,
        to_currency=target_currency,
        rate=rate,
    )
    if total_budget is not None:
        estimate = add_budget_comparison(estimate, total_budget)

    estimate["api_used"] = True
    estimate["pricing_source"] = (
        f"{estimate['pricing_source']}_converted_with_frankfurter"
    )
    return estimate
