"""Persisted trip preferences.

Replaces the previous in-memory dict with a database-backed store, keeping
the same `get_trip` / `update_trip` interface used by `ChatService`.
"""
from app.database.session import get_session
from app.models.trip import TripRecord
from app.schemas.trip import TripPreferences, TripPreferenceUpdate


def _record_to_preferences(record: TripRecord | None) -> TripPreferences:
    if record is None:
        return TripPreferences()

    return TripPreferences(
        destination=record.destination,
        travel_date=record.travel_date,
        budget=record.budget,
        travelers=record.travelers,
        duration_days=record.duration_days,
    )


class TripStore:
    def get_trip(
        self,
        conversation_id: str,
    ) -> TripPreferences:
        session = get_session()
        try:
            record = session.get(TripRecord, conversation_id)
            return _record_to_preferences(record)
        finally:
            session.close()

    def update_trip(
        self,
        conversation_id: str,
        updates: TripPreferenceUpdate,
    ) -> TripPreferences:
        update_data = updates.model_dump(exclude_none=True)

        session = get_session()
        try:
            record = session.get(TripRecord, conversation_id)
            if record is None:
                record = TripRecord(conversation_id=conversation_id)
                session.add(record)

            for field, value in update_data.items():
                setattr(record, field, value)

            session.commit()
            session.refresh(record)

            return _record_to_preferences(record)
        finally:
            session.close()
