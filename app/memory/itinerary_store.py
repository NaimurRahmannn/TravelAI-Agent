from app.schemas.itinerary import Itinerary


class ItineraryStore:
    def __init__(self):
        self._itineraries: dict[str, Itinerary] = {}

    def get_itinerary(
        self,
        conversation_id: str,
    ) -> Itinerary | None:
        return self._itineraries.get(conversation_id)

    def save_itinerary(
        self,
        conversation_id: str,
        itinerary: Itinerary,
    ) -> None:
        self._itineraries[conversation_id] = itinerary