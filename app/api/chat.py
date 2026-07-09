from fastapi import APIRouter

from app.chains.travel_chain import travel_chain
from app.memory.conversation_store import ConversationStore
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService


router = APIRouter()

conversation_store = ConversationStore()

travel_chat_service = ChatService(
    travel_chain,
    conversation_store,
)


@router.post(
    "/chat",
    response_model=ChatResponse,
)
def chat(request: ChatRequest):
    conversation_id, response = (
        travel_chat_service.generate_response(
            message=request.message,
            conversation_id=request.conversation_id,
        )
    )

    return ChatResponse(
        conversation_id=conversation_id,
        response=response,
    )