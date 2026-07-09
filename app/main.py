from fastapi import FastAPI
from app.core.config import settings
from app.llm import get_llm
from app.prompts.travel_prompt import travel_prompt
from app.chains.travel_chain import travel_chain
app = FastAPI(
    title=settings.app_name,
    description="AI-powered travel planning assistant",
    version=settings.app_version,
)



@app.get("/")
def root():
    try:
        response =travel_chain.invoke({
            "destination":"Japan",
            "budget":"$2000",
            })
        return {
        "message": "Travel AI API is running",
        "model": settings.gemini_model,
        "response": response,
    }
    except Exception as e:
        return {"error": str(e)} 
    


@app.get("/health")
def health():
    return {"status": "health", "service": "travel-ai"}
