from fastapi import FastAPI
from app.core.config import settings
from app.llm import get_llm
app=FastAPI(
    title=settings.app_name,
    description="AI-powered travel planning assistant",
    version=settings.app_version
)
llm=get_llm()
@app.get("/")
def root():
    response=llm.invoke("say hello in one sentence")
    return {"message": "Travel AI API is running",
            "model":settings.gemini_model,
            "response":response
            }

@app.get("/health")
def health():
    return{
        "status":"health",
        "service":"travel-ai"
    }