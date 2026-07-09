from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    conversation_id: str
    response: str