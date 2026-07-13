"""Persisted conversation history.

Replaces the previous in-memory implementation. Conversation turns are
written to the database so they survive process restarts, while exposing
the same minimal interface the rest of the app relies on:
`get_history(conversation_id).messages` and `.add_messages([...])`.
"""
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from app.database.session import get_session
from app.models.conversation import ConversationMessage

_ROLE_TO_MESSAGE_CLS = {
    "human": HumanMessage,
    "ai": AIMessage,
}
_MESSAGE_CLS_TO_ROLE = {
    HumanMessage: "human",
    AIMessage: "ai",
}


class PersistedChatMessageHistory:
    """Chat message history for one conversation, backed by the database.

    Implements the small slice of LangChain's `BaseChatMessageHistory`
    interface that `ChatService` uses (`.messages`, `.add_messages`), so it
    is a drop-in replacement for `InMemoryChatMessageHistory`.
    """

    def __init__(self, conversation_id: str):
        self.conversation_id = conversation_id

    @property
    def messages(self) -> list[BaseMessage]:
        session = get_session()
        try:
            rows = (
                session.query(ConversationMessage)
                .filter_by(conversation_id=self.conversation_id)
                .order_by(ConversationMessage.id)
                .all()
            )
            return [
                _ROLE_TO_MESSAGE_CLS.get(row.role, HumanMessage)(
                    content=row.content
                )
                for row in rows
            ]
        finally:
            session.close()

    def add_messages(self, messages: list[BaseMessage]) -> None:
        if not messages:
            return

        session = get_session()
        try:
            for message in messages:
                role = _MESSAGE_CLS_TO_ROLE.get(type(message), "human")
                session.add(
                    ConversationMessage(
                        conversation_id=self.conversation_id,
                        role=role,
                        content=str(message.content),
                    )
                )
            session.commit()
        finally:
            session.close()

    def clear(self) -> None:
        session = get_session()
        try:
            session.query(ConversationMessage).filter_by(
                conversation_id=self.conversation_id
            ).delete()
            session.commit()
        finally:
            session.close()


class ConversationStore:
    def get_history(
        self,
        conversation_id: str,
    ) -> PersistedChatMessageHistory:
        return PersistedChatMessageHistory(conversation_id)
