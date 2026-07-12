from app.llm import get_llm
from app.prompts.travel_prompt import travel_prompt
from app.tools import TRAVEL_TOOLS

llm = get_llm().bind_tools(TRAVEL_TOOLS)

travel_chain = travel_prompt | llm
