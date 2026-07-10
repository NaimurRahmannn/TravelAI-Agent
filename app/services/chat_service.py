from uuid import uuid4

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
)

from app.memory.conversation_store import ConversationStore
from app.memory.itinerary_store import ItineraryStore
from app.memory.trip_store import TripStore
from app.services.clarification_service import ClarificationService


class ChatService:
    def __init__(
        self,
        chain,
        trip_extraction_chain,
        itinerary_chain,
        conversation_store: ConversationStore,
        trip_store: TripStore,
        itinerary_store: ItineraryStore,
        clarification_service: ClarificationService,
    ):
        self.chain = chain
        self.trip_extraction_chain = trip_extraction_chain
        self.itinerary_chain = itinerary_chain
        self.conversation_store = conversation_store
        self.trip_store = trip_store
        self.itinerary_store = itinerary_store
        self.clarification_service = clarification_service

    def generate_response(
        self,
        message: str,
        conversation_id: str | None = None,
    ):
        message = " ".join(message.split())

        conversation_id = conversation_id or str(uuid4())

        history = self.conversation_store.get_history(
            conversation_id
        )

        current_trip = self.trip_store.get_trip(
            conversation_id
        )

        extracted_updates = self.trip_extraction_chain.invoke(
            {
                "trip_context": current_trip.model_dump_json(),
                "user_input": message,
            }
        )

        trip_preferences = self.trip_store.update_trip(
            conversation_id,
            extracted_updates,
        )

        itinerary = self.itinerary_store.get_itinerary(
            conversation_id
        )

        clarification_question = (
            self.clarification_service.get_next_question(
                trip_preferences
            )
        )

        if clarification_question:
            response = clarification_question

        elif itinerary is None:
            itinerary = self.itinerary_chain.invoke(
                {
                    "trip_context": (
                        trip_preferences.model_dump_json()
                    ),
                }
            )

            self.itinerary_store.save_itinerary(
                conversation_id,
                itinerary,
            )

            response = (
                f"I created your "
                f"{trip_preferences.duration_days}-day "
                f"{trip_preferences.destination} itinerary."
            )

        else:
            response = self.chain.invoke(
                {
                    "history": history.messages,
                    "user_input": message,
                    "trip_context": (
                        trip_preferences.model_dump_json()
                    ),
                }
            )

        history.add_messages(
            [
                HumanMessage(content=message),
                AIMessage(content=response),
            ]
        )

        return (
            conversation_id,
            response,
            trip_preferences,
            itinerary,
        )