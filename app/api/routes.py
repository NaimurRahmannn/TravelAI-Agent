from fastapi import APIRouter
from app.chains.travel_chain import travel_chain
from app.schemas.chat import ChatRequest,ChatResponse

router=APIRouter()

@router.post("/chat",response_model=ChatResponse)
def chat(request:ChatRequest):
    response=travel_chain.invoke(
        {
            "user_input":request.message
        }
    )
    return ChatResponse(
        response=response
    )