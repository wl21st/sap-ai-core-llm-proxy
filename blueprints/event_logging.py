"""Blueprint for /api/event_logging/batch endpoint."""

from flask import Blueprint, jsonify, request

from utils.logging_utils import get_server_logger

logger = get_server_logger(__name__)

event_logging_bp = Blueprint("event_logging", __name__)


@event_logging_bp.route("/api/event_logging/batch", methods=["POST", "OPTIONS"])
def handle_event_logging():
    """Dummy endpoint for Claude Code event logging to prevent 404 errors."""
    logger.info("Received request to /api/event_logging/batch")
    logger.debug(f"Request headers: {request.headers}")
    logger.debug(f"Request body: {request.get_json(silent=True)}")

    # Return success response for event logging
    return jsonify({"status": "success", "message": "Events logged successfully"}), 200
