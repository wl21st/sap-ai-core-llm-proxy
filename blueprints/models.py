"""Blueprint for /v1/models endpoint."""

import time
from typing import Any, TYPE_CHECKING

from flask import Blueprint, Response, jsonify

from utils.logging_utils import get_server_logger

if TYPE_CHECKING:
    from config import ProxyConfig, ProxyGlobalContext

logger = get_server_logger(__name__)

models_bp = Blueprint("models", __name__)

# These will be set by register_blueprints() in proxy_server.py
_proxy_config: "ProxyConfig" = None  # type: ignore
_ctx: "ProxyGlobalContext" = None  # type: ignore


def init_models_blueprint(
    proxy_config: "ProxyConfig", ctx: "ProxyGlobalContext"
) -> None:
    """Initialize blueprint with configuration and context.

    Args:
        proxy_config: The proxy configuration
        ctx: The global context
    """
    global _proxy_config, _ctx
    _proxy_config = proxy_config
    _ctx = ctx


@models_bp.route("/v1/models", methods=["GET", "OPTIONS"])
def list_models() -> tuple[Response, int]:
    """Lists all available models across all subAccounts."""
    logger.info("Received request to /v1/models")

    models: list[dict[str, Any]] = []
    timestamp = int(time.time())

    for model_name in _proxy_config.model_to_subaccounts.keys():
        models.append(
            {
                "id": model_name,
                "object": "model",
                "created": timestamp,
                "owned_by": "sap-ai-core",
            }
        )

    return jsonify({"object": "list", "data": models}), 200
