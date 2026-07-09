from fastapi import FastAPI
from app.core.config import settings
from app.api.routes import router
app = FastAPI(
    title=settings.app_name,
    description="AI-powered travel planning assistant",
    version=settings.app_version,
)


app.include_router(router)



