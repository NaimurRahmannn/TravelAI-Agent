from pydantic import BaseModel
from app.schemas.trip import TripPreferences
from app.schemas.itinerary import Itinerary
class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    conversation_id: str
    response: str
    trip_preferences:TripPreferences
    itinerary: Itinerary|None=None