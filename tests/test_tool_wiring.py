from langchain_core.messages import AIMessage
from langchain_core.tools import tool

from app.services.chat_service import ChatService
from app.tools import TRAVEL_TOOL_NAMES, TRAVEL_TOOLS
from app.tools.tool_executor import ToolExecutor


def test_all_implemented_travel_tools_are_registered():
    assert set(TRAVEL_TOOL_NAMES) == {
        "get_destination_info",
        "estimate_travel_budget",
        "convert_currency",
        "get_current_weather",
        "geocode_place",
        "reverse_geocode",
        "get_route",
        "find_nearby_places",
        "cluster_places",
        "travel_time_matrix",
        "map_bounds",
    }
    assert len(TRAVEL_TOOLS) == len(TRAVEL_TOOL_NAMES)


def test_chat_service_executes_tool_calls_before_final_response():
    @tool
    def sample_destination_tool(destination: str) -> dict:
        """Return a deterministic destination record."""
        return {"destination": destination, "status": "ok"}

    class FakeChain:
        def __init__(self):
            self.calls = []

        def invoke(self, payload):
            self.calls.append(payload)
            if len(self.calls) == 1:
                return AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "sample_destination_tool",
                            "args": {"destination": "Tokyo"},
                            "id": "call-1",
                        }
                    ],
                )

            assert any(
                getattr(message, "tool_call_id", None) == "call-1"
                for message in payload["history"]
            )
            return AIMessage(content="Tokyo is ready for planning.")

    service = ChatService(
        chain=FakeChain(),
        trip_extraction_chain=None,
        itinerary_chain=None,
        conversation_store=None,
        trip_store=None,
        itinerary_store=None,
        clarification_service=None,
        tool_executor=ToolExecutor([sample_destination_tool]),
    )

    response = service._generate_tool_augmented_response(
        history=[],
        message="Tell me about Tokyo",
        trip_context="{}",
    )

    assert response == "Tokyo is ready for planning."
