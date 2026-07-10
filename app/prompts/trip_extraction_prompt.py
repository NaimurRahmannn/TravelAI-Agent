from langchain_core.prompts import ChatPromptTemplate


trip_extraction_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
You extract updates to a travel trip.

Current trip:
{trip_context}

Extract only travel information explicitly stated or changed
in the current user message.

Do not repeat existing values unless the user explicitly
mentions or changes them.

Do not guess missing information.
            """,
        ),
        (
            "human",
            "{user_input}",
        ),
    ]
)