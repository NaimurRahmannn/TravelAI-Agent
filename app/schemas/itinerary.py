from pydantic import BaseModel, Field


class Activity(BaseModel):
    name: str = Field(description="Name of the travel activity")
    description: str = Field(description="Short description of the activity")
    estimated_cost: float = Field(description="Estimated cost of the activity")


class ItineraryDay(BaseModel):
    day: int = Field(description="Trip day number")
    activities: list[Activity]


class Itinerary(BaseModel):
    destination: str
    days: list[ItineraryDay]
    estimated_total_cost: float
