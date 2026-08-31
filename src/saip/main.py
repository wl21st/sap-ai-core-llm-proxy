from contextlib import asynccontextmanager
from typing import AsyncIterator
import logging

from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from saip.cli import parse_arguments
from saip.config import ProxyConfig, ProxyGlobalContext, load_proxy_config
from saip.routers import chat, embeddings, logging as logging_router, messages, models, status
from saip.utils.logging_utils import init_logging
from saip.utils.metrics import MetricsCollector
from saip.utils.metrics_middleware import MetricsMiddleware

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
    app.state.metrics = MetricsCollector()
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

    app.add_middleware(MetricsMiddleware)

    app.include_router(chat.router)
    app.include_router(messages.router)
    app.include_router(embeddings.router)
    app.include_router(models.router)
    app.include_router(logging_router.router)
    app.include_router(status.router)
    return app


def main() -> None:
    import sys
    import os
    import uvicorn

    args = parse_arguments()
    config_path: str = args.config
    init_logging(debug=args.debug)

    try:
        proxy_config = load_proxy_config(config_path)
    except FileNotFoundError:
        logger.error(
            "\n"
            "================================================================================\n"
            "❌ CONFIGURATION ERROR: Configuration file not found!\n"
            "================================================================================\n"
            f"Could not find configuration file '{config_path}' in:\n"
            f"  • Current directory: {os.getcwd()}\n"
            f"  • Parent directories up to project root\n"
            f"  • Environment variable: SAP_AI_PROXY_CONFIG / CONFIG_PATH\n\n"
            "💡 Troubleshooting Tips:\n"
            "  1. Copy the example configuration to get started:\n"
            "       cp config.json.example config.json\n"
            "  2. Specify a custom configuration file path:\n"
            f"       saip -c /path/to/{config_path}\n"
            "  3. Set the SAP_AI_PROXY_CONFIG environment variable:\n"
            f"       export SAP_AI_PROXY_CONFIG=/path/to/{config_path}\n"
            "================================================================================"
        )
        sys.exit(1)
    except Exception as e:
        logger.error(
            "\n"
            "================================================================================\n"
            "❌ CONFIGURATION ERROR: Failed to load configuration!\n"
            "================================================================================\n"
            f"Error details: {e}\n\n"
            "💡 Troubleshooting Tips:\n"
            "  1. Validate that your configuration file is valid JSON.\n"
            "  2. Verify all referenced service key JSON files exist and have valid credentials.\n"
            "  3. Check the schema against config.json.example.\n"
            "================================================================================"
        )
        sys.exit(1)

    app = create_app(config_path)
    host = proxy_config.host
    port = proxy_config.port
    if args.port is not None:
        port = args.port

    logger.info(f"Starting SAP AI Core Proxy on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


def get_proxy_config(app: FastAPI) -> ProxyConfig:
    return app.state.proxy_config


def get_proxy_context(app: FastAPI) -> ProxyGlobalContext:
    return app.state.proxy_context
