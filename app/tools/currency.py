import httpx
from langchain.tools import tool


CURRENCY_API_URL = (
    "https://api.frankfurter.dev/v2/rate"
)


@tool
def convert_currency(
    amount: float,
    from_currency: str,
    to_currency: str,
) -> dict:
    """Convert money from one currency to another."""

    from_currency = from_currency.upper()
    to_currency = to_currency.upper()

    response = httpx.get(
        (
            f"{CURRENCY_API_URL}/"
            f"{from_currency}/"
            f"{to_currency}"
        ),
        timeout=10,
    )

    response.raise_for_status()

    data = response.json()

    rate = data["rate"]

    converted_amount = amount * rate

    return {
        "amount": amount,
        "from_currency": from_currency,
        "to_currency": to_currency,
        "rate": rate,
        "converted_amount": round(
            converted_amount,
            2,
        ),
    }