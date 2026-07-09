from langchain_core.output_parsers import StrOutputParser

from app.llm import get_llm
from app.prompts.travel_prompt import travel_prompt

llm=get_llm()

travel_chain = travel_prompt | llm | StrOutputParser()
