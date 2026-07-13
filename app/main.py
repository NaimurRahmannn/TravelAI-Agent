from fastapi import FastAPI
from app.core.config import settings
from app.api.routes import router
from app.database.session import init_db
app = FastAPI(
    title=settings.app_name,
    description="AI-powered travel planning assistant",
    version=settings.app_version,
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()



app.include_router(router)



