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

    travellers: int | None = Field(
        default=None,
        description="Number of travelers",
    )
    def get_missing_fields(self)->list[str]:
        required_fields=[
            "destination",
            "travel_date",
            "budget",
            "travellers",
        ]
        return[
            field 
            for field in required_fields
            if getattr(self,field)is None
        ]
class TripPreferenceUpdate(BaseModel):
    destination: str | None = None
    travel_date: str | None = None
    budget: float | None = None
    travelers: int | None = None