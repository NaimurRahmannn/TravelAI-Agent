from langchain_core.prompts import ChatPromptTemplate

travel_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
You are an experienced travel planner.

Your responsibilities are:

- Recommend realistic travel plans.
- Ask clarifying questions when necessary.
- Consider budget.
- Consider weather.
- Be concise and helpful.
            """,
        ),
        (
            "human",
            """
           {user_input}
"""
        ),
    ]
)
