"""Persisted itineraries.

Replaces the previous in-memory dict with a database-backed store, keeping
the same `get_itinerary` / `save_itinerary` / `delete_itinerary` interface
used by `ChatService`.
"""
from app.database.session import get_session
from app.models.itinerary import ItineraryRecord
from app.schemas.itinerary import Itinerary


class ItineraryStore:
    def get_itinerary(
        self,
        conversation_id: str,
    ) -> Itinerary | None:
        session = get_session()
        try:
            record = session.get(ItineraryRecord, conversation_id)
            if record is None:
                return None

            return Itinerary(
                destination=record.destination,
                days=record.days,
                estimated_total_cost=record.estimated_total_cost,
            )
        finally:
            session.close()

    def save_itinerary(
        self,
        conversation_id: str,
        itinerary: Itinerary,
    ) -> None:
        session = get_session()
        try:
            record = session.get(ItineraryRecord, conversation_id)
            if record is None:
                record = ItineraryRecord(conversation_id=conversation_id)
                session.add(record)

            record.destination = itinerary.destination
            record.days = [day.model_dump() for day in itinerary.days]
            record.estimated_total_cost = itinerary.estimated_total_cost

            session.commit()
        finally:
            session.close()

    def delete_itinerary(
        self,
        conversation_id: str,
    ) -> None:
        session = get_session()
        try:
            session.query(ItineraryRecord).filter_by(
                conversation_id=conversation_id
            ).delete()
            session.commit()
        finally:
            session.close()
