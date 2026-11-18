from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.llm.errors import LLMProviderError, LLMResponseValidationError, LLMTimeoutError


def register_exception_handlers(app: FastAPI) -> None:
    """Translate LLM domain errors into HTTP status codes.

    Called once from app.main — defining handlers here instead keeps
    main.py readable and avoids a circular import.
    """

    @app.exception_handler(LLMTimeoutError)
    async def timeout_handler(request: Request, exc: LLMTimeoutError) -> JSONResponse:
        return JSONResponse(
            status_code=504,
            content={"detail": "The model did not respond in time."},
        )

    @app.exception_handler(LLMProviderError)
    async def provider_handler(request: Request, exc: LLMProviderError) -> JSONResponse:
        return JSONResponse(
            status_code=502,
            content={"detail": "The model provider failed."},
        )

    @app.exception_handler(LLMResponseValidationError)
    async def validation_handler(
        request: Request, exc: LLMResponseValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=502,
            content={"detail": "The model returned an invalid response."},
        )
