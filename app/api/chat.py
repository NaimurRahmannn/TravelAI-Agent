from fastapi import APIRouter

from app.chains.travel_chain import travel_chain
from app.chains.trip_extraction_chain import (
    trip_extraction_chain,
)
from app.memory.conversation_store import ConversationStore
from app.memory.trip_store import TripStore
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService
from app.services.clarification_service import ClarificationService
from app.chains.itinerary_chain import itinerary_chain
from app.memory.itinerary_store import ItineraryStore

router = APIRouter()

conversation_store = ConversationStore()
trip_store = TripStore()
itinerary_store = ItineraryStore()
clarification_service = ClarificationService()
travel_chat_service = ChatService(
    chain=travel_chain,
    trip_extraction_chain=trip_extraction_chain,
    itinerary_chain=itinerary_chain,
    conversation_store=conversation_store,
    trip_store=trip_store,
    itinerary_store=itinerary_store,
    clarification_service=clarification_service
)
@router.post(
    "/chat",
    response_model=ChatResponse,
)
def chat(request: ChatRequest):
    (
        conversation_id,
        response,
        trip_preferences,
        itinerary,
    ) = travel_chat_service.generate_response(
        message=request.message,
        conversation_id=request.conversation_id,
    )

    return ChatResponse(
        conversation_id=conversation_id,
        response=response,
        trip_preferences=trip_preferences,
        itinerary=itinerary
    )
