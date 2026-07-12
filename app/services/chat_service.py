from uuid import uuid4

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
)

from app.memory.conversation_store import ConversationStore
from app.memory.itinerary_store import ItineraryStore
from app.memory.trip_store import TripStore
from app.services.clarification_service import ClarificationService
from app.tools import TRAVEL_TOOLS
from app.tools.tool_executor import ToolExecutor


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
        tool_executor: ToolExecutor | None = None,
    ):
        self.chain = chain
        self.trip_extraction_chain = trip_extraction_chain
        self.itinerary_chain = itinerary_chain
        self.conversation_store = conversation_store
        self.trip_store = trip_store
        self.itinerary_store = itinerary_store
        self.clarification_service = clarification_service
        self.tool_executor = tool_executor or ToolExecutor(TRAVEL_TOOLS)

    def generate_response(
        self,
        message: str,
        conversation_id: str | None = None,
    ):
        message = " ".join(message.split())

        conversation_id = conversation_id or str(uuid4())

        history = self.conversation_store.get_history(conversation_id)

        current_trip = self.trip_store.get_trip(conversation_id)

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
        trip_changed = current_trip.model_dump() != trip_preferences.model_dump()
        if trip_changed:
            self.itinerary_store.delete_itinerary(conversation_id)
        itinerary = self.itinerary_store.get_itinerary(conversation_id)
        clarification_question = self.clarification_service.get_next_question(
            trip_preferences
        )

        if clarification_question:
            response = clarification_question

        elif itinerary is None:
            itinerary = self.itinerary_chain.invoke(
                {
                    "trip_context": (trip_preferences.model_dump_json()),
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
            response = self._generate_tool_augmented_response(
                history=history.messages,
                message=message,
                trip_context=trip_preferences.model_dump_json(),
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

    def _generate_tool_augmented_response(
        self,
        history: list,
        message: str,
        trip_context: str,
    ) -> str:
        tool_history = list(history)
        response_message = self.chain.invoke(
            {
                "history": tool_history,
                "user_input": message,
                "trip_context": trip_context,
            }
        )

        for _ in range(3):
            tool_calls = getattr(response_message, "tool_calls", None) or []
            if not tool_calls:
                return str(response_message.content)

            tool_messages = [
                self.tool_executor.execute(tool_call)
                for tool_call in tool_calls
            ]
            tool_history = [
                *tool_history,
                HumanMessage(content=message),
                response_message,
                *tool_messages,
            ]
            response_message = self.chain.invoke(
                {
                    "history": tool_history,
                    "user_input": (
                        "Use the tool results above to answer the user's "
                        "travel question."
                    ),
                    "trip_context": trip_context,
                }
            )

        return str(response_message.content)
