from contextlib import asynccontextmanager
from typing import AsyncIterator
import logging

from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from cli import parse_arguments
from config import ProxyConfig, ProxyGlobalContext, load_proxy_config
from routers import chat, embeddings, logging as logging_router, messages, models
from utils.logging_utils import init_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    config_path = app.state.config_path
    config = load_proxy_config(config_path)
    init_logging(debug=True)
    context = ProxyGlobalContext()
    context.initialize(config)
    app.state.proxy_config = config
    app.state.proxy_context = context
    yield
    context.shutdown()


def create_app(config_path: str) -> FastAPI:
    """Create and configure FastAPI application instance.

    Factory function that creates a FastAPI app with all routers registered
    and configuration initialized via lifespan context manager.

    Args:
        config_path: Path to config.json file

    Returns:
        Configured FastAPI application instance

    Registered Routers:
        - chat.router: /v1/chat/completions endpoint
        - messages.router: /v1/messages endpoint (Claude Messages API)
        - embeddings.router: /v1/embeddings endpoint
        - models.router: /v1/models endpoint
        - logging_router: /api/event_logging endpoint

    Notes:
        - Stores config_path in app.state for lifespan manager
        - Lifespan manager handles startup/shutdown logic
        - All routes use verify_request_token dependency for auth
        - Global exception handlers ensure JSON responses for all errors
    """
    app = FastAPI(lifespan=lifespan)
    app.state.config_path = config_path

    # Register global exception handlers
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Handle Pydantic validation errors with JSON response."""
        logger.warning(
            "Validation error: %s, errors: %s",
            request.url,
            exc.errors(),
        )
        return JSONResponse(
            status_code=422,
            content={
                "error": "Request validation failed",
                "type": "validation_error",
                "details": exc.errors(),
            },
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request, exc: HTTPException
    ) -> JSONResponse:
        """Handle FastAPI HTTP exceptions with JSON response."""
        logger.error(
            "HTTP exception: %s, status: %s, detail: %s",
            request.url,
            exc.status_code,
            exc.detail,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.detail,
                "type": "http_error",
            },
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Handle all unhandled exceptions with JSON response."""
        logger.error(
            "Unhandled exception: %s, error: %s",
            request.url,
            exc,
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "type": "internal_error",
            },
        )

    app.include_router(chat.router)
    app.include_router(messages.router)
    app.include_router(embeddings.router)
    app.include_router(models.router)
    app.include_router(logging_router.router)
    return app


def main() -> None:
    import uvicorn

    args = parse_arguments()
    config_path: str = args.config
    init_logging(debug=args.debug)
    app = create_app(config_path)
    proxy_config = load_proxy_config(config_path)
    host = proxy_config.host
    port = proxy_config.port
    if args.port is not None:
        port = args.port
    uvicorn.run(app, host=host, port=port, log_level="info")


def get_proxy_config(app: FastAPI) -> ProxyConfig:
    return app.state.proxy_config


def get_proxy_context(app: FastAPI) -> ProxyGlobalContext:
    return app.state.proxy_context
