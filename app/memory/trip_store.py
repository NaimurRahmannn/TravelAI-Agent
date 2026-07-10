from app.schemas.trip import TripPreferences,TripPreferenceUpdate


class TripStore:
    def __init__(self):
        self._trips: dict[str, TripPreferences] = {}

    def get_trip(
        self,
        conversation_id: str,
    ) -> TripPreferences:
        if conversation_id not in self._trips:
            self._trips[conversation_id] = TripPreferences()

        return self._trips[conversation_id]

    def update_trip(
        self,
        conversation_id: str,
        updates: TripPreferenceUpdate,
    ) -> TripPreferences:
        current_trip = self.get_trip(conversation_id)

        update_data = updates.model_dump(
            exclude_none=True
        )

        updated_trip = current_trip.model_copy(
            update=update_data
        )

        self._trips[conversation_id] = updated_trip

        return updated_trip