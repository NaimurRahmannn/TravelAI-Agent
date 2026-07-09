from fastapi import FastAPI
from app.core.config import settings
app=FastAPI(
    title=settings.app_name,
    description="AI-powered travel planning assistant",
    version=settings.app_version
)
@app.get("/")
def root():
    return {"message": "Travel AI API is running",
            "model":settings.gemini_model,
            }

@app.get("/health")
def health():
    return{
        "status":"health",
        "service":"travel-ai"
    }