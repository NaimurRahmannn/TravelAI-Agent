from uuid import uuid4

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
)

from app.memory.conversation_store import ConversationStore


class ChatService:
    def __init__(
        self,
        chain,
        conversation_store: ConversationStore,
    ):
        self.chain = chain
        self.conversation_store = conversation_store

    def generate_response(
        self,
        message: str,
        conversation_id: str | None = None,
    ) -> tuple[str, str]:
        message = " ".join(message.split())

        conversation_id = (
            conversation_id or str(uuid4())
        )

        history = self.conversation_store.get_history(
            conversation_id
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

        return conversation_id, response