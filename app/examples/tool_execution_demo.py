from langchain_core.messages import (
    HumanMessage,
    SystemMessage,
)

from app.llm import get_llm
from app.tools.currency import convert_currency
from app.tools.destination_tool import get_destination_info
from app.tools.tool_executor import ToolExecutor
from app.tools.weather import get_current_weather


llm = get_llm()

tools = [
    get_destination_info,
    get_current_weather,
    convert_currency,
]

tool_executor = ToolExecutor(tools)

llm_with_tools = llm.bind_tools(tools)


messages = [
    SystemMessage(
        content="""
You are a travel assistant.

Use tools when real-time data is required.

Never invent weather forecasts.

If an exact weather forecast is not available for a future date,
clearly say so.

You may describe typical seasonal weather, but clearly label it
as typical climate conditions, not a weather forecast.
        """
    ),
    HumanMessage(
        content=(
            "Tell me about Tokyo and what will the weather"
            "be in Japan next October? and convert the 20000BDT in jpy"
        )
    ),
]


ai_message = llm_with_tools.invoke(messages)


print("TOOL CALLS:")
print(ai_message.tool_calls)


tool_messages = []

for tool_call in ai_message.tool_calls:
    tool_message = tool_executor.execute(
        tool_call
    )

    tool_messages.append(tool_message)


final_response = llm_with_tools.invoke(
    [
        *messages,
        ai_message,
        *tool_messages,
    ]
)


print("\nFINAL RESPONSE:")
print(final_response.content)