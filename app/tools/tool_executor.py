from langchain_core.messages import ToolMessage


class ToolExecutor:
    def __init__(self, tools: list):
        self.tools = {
            tool.name: tool
            for tool in tools
        }

    def execute(
        self,
        tool_call: dict,
    ) -> ToolMessage:
        tool_name = tool_call["name"]

        tool = self.tools.get(tool_name)

        if tool is None:
            raise ValueError(
                f"Unknown tool: {tool_name}"
            )

        result = tool.invoke(
            tool_call["args"]
        )

        return ToolMessage(
            content=str(result),
            tool_call_id=tool_call["id"],
        )