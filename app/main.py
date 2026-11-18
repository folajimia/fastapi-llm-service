from fastapi import FastAPI

from app.api.errors import register_exception_handlers
from app.api.router import api_router

app = FastAPI(
    title="LLM Services",
    version="0.1.0",
)

app.include_router(api_router, prefix="/api/v1")
register_exception_handlers(app)
