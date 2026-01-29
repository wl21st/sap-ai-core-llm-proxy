"""Flask Blueprints for SAP AI Core LLM Proxy."""

from blueprints.chat_completions import (
    chat_completions_bp,
    init_chat_completions_blueprint,
)
from blueprints.messages import messages_bp, init_messages_blueprint
from blueprints.embeddings import embeddings_bp, init_embeddings_blueprint
from blueprints.models import models_bp, init_models_blueprint
from blueprints.event_logging import event_logging_bp

__all__ = [
    "chat_completions_bp",
    "messages_bp",
    "embeddings_bp",
    "models_bp",
    "event_logging_bp",
    "init_chat_completions_blueprint",
    "init_messages_blueprint",
    "init_embeddings_blueprint",
    "init_models_blueprint",
]
