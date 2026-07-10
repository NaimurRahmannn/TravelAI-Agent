from uuid import uuid4

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
)

from app.memory.conversation_store import ConversationStore
from app.memory.trip_store import TripStore


class ChatService:
    def __init__(
        self,
        chain,
        trip_extraction_chain,
        conversation_store: ConversationStore,
        trip_store: TripStore,
    ):
        self.chain = chain
        self.trip_extraction_chain = trip_extraction_chain
        self.conversation_store = conversation_store
        self.trip_store = trip_store

    def generate_response(
        self,
        message: str,
        conversation_id: str | None = None,
    ):
        message = " ".join(message.split())

        conversation_id = (
            conversation_id or str(uuid4())
        )

        history = self.conversation_store.get_history(
            conversation_id
        )

        extracted_preferences = (
            self.trip_extraction_chain.invoke(
                {
                    "history": history.messages,
                    "user_input": message,
                }
            )
        )

        trip_preferences = self.trip_store.update_trip(
            conversation_id,
            extracted_preferences,
        )

        response = self.chain.invoke(
            {
                "history": history.messages,
                "user_input": message,
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
        )