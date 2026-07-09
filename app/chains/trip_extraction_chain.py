from app.llm import get_llm
from app.prompts.trip_extraction_prompt import (
    trip_extraction_prompt,
)
from app.schemas.trip import TripPreferences


llm = get_llm()

structured_llm = llm.with_structured_output(
    TripPreferences
)

trip_extraction_chain = (
    trip_extraction_prompt
    | structured_llm
)