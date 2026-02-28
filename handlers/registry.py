"""Model handler registry and protocol definitions."""

from __future__ import annotations

from typing import Callable, Protocol

from utils.logging_utils import get_server_logger

logger = get_server_logger(__name__)


class ModelHandler(Protocol):
    """Protocol for model handlers."""

    def handle_request(self, request: dict, config, ctx):
        """Handle a non-streaming request."""

    def handle_streaming(self, request: dict, config, ctx):
        """Handle a streaming request."""

    def get_converter(self):
        """Return converter for responses, if any."""


class ModelHandlerRegistry:
    """Registry for model handlers keyed by detector functions."""

    _handlers: list[tuple[Callable[[str], bool], type[ModelHandler]]] = []

    @classmethod
    def register(cls, detector: Callable[[str], bool]):
        def decorator(handler_cls: type[ModelHandler]):
            cls._handlers.append((detector, handler_cls))
            return handler_cls

        return decorator

    @classmethod
    def get_handler(cls, model: str) -> ModelHandler:
        for detector, handler_cls in cls._handlers:
            if detector(model):
                return handler_cls()

        logger.warning(
            "No handler matched model '%s'; falling back to DefaultHandler.",
            model,
        )
        from handlers.base_handler import DefaultHandler

        return DefaultHandler()
