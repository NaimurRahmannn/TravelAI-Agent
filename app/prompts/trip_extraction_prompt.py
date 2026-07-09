from langchain_core.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
)


trip_extraction_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
Extract travel preferences from the conversation.

Only extract information explicitly provided by the user.
Do not guess missing information.
            """,
        ),
        MessagesPlaceholder(
            variable_name="history",
            optional=True,
        ),
        (
            "human",
            "{user_input}",
        ),
    ]
)