from fastapi import FastAPI
from src.apis.routes import router as api_router # type: ignore
from src.helper.config import get_settings  # type: ignore

settings = get_settings()
app = FastAPI(title=settings.PROJECT_NAME)

app.include_router(api_router, prefix="/api")

@app.get("/")
async def root():
    return { "message": "Welcome to the Multi-Agent API" }

@app.get("/health")
async def health():
    return { "status": "ok" }