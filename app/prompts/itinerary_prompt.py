from langchain_core.prompts import ChatPromptTemplate


itinerary_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
You are an expert travel itinerary planner.

Create a realistic day-by-day itinerary.

Rules:
- Respect the travel budget.
- Respect the number of travelers.
- Generate exactly the requested number of days.
- Recommend realistic activities.
- Keep estimated costs reasonable.
- Do not invent additional trip preferences.

Trip preferences:
{trip_context}
            """,
        ),
    ]
)