from langchain_core.chat_history import InMemoryChatMessageHistory


class ConversationStore:
    def __init__(self):
        self._histories: dict[str, InMemoryChatMessageHistory] = {}

    def get_history(
        self,
        conversation_id: str,
    ) -> InMemoryChatMessageHistory:
        if conversation_id not in self._histories:
            self._histories[conversation_id] = (
                InMemoryChatMessageHistory()
            )

        return self._histories[conversation_id]