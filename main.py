from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from cli import parse_arguments
from config import ProxyConfig, ProxyGlobalContext, load_proxy_config
from routers import chat, embeddings, logging as logging_router, messages, models
from utils.logging_utils import init_logging


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
    app = FastAPI(lifespan=lifespan)
    app.state.config_path = config_path
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
