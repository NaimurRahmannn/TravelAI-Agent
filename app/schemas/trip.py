from pydantic import BaseModel, Field


class TripPreferences(BaseModel):
    destination: str | None = Field(
        default=None,
        description="Travel destination",
    )

    travel_date: str | None = Field(
        default=None,
        description="Travel date, month, or time period",
    )

    budget: float | None = Field(
        default=None,
        description="Traveler budget",
    )

    travelers: int | None = Field(
        default=None,
        description="Number of travelers",
    )