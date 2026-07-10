from app.llm import get_llm

from app.prompts.itinerary_prompt import itinerary_prompt
from app.schemas.itinerary import Itinerary

llm=get_llm()

structured_llm=llm.with_structured_output(
    Itinerary
)

iternerary_chain=(
    itinerary_prompt|structured_llm
)