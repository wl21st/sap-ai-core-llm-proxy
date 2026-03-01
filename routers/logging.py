"""Router for /api/event_logging/batch endpoint."""

import json

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from utils.logging_utils import get_server_logger

logger = get_server_logger(__name__)

router = APIRouter()


@router.post("/api/event_logging/batch")
@router.options("/api/event_logging/batch")
async def handle_event_logging(request: Request) -> JSONResponse:
    """Dummy endpoint for Claude Code event logging to prevent 404 errors.

    Handles both POST and OPTIONS (CORS preflight) requests gracefully.
    """
    logger.info("Received %s request to /api/event_logging/batch", request.method)
    logger.debug("Request headers: %s", request.headers)

    # Only read body for POST requests (OPTIONS has empty body)
    if request.method == "POST":
        try:
            body = await request.json()
            logger.debug("Request body: %s", body)
        except json.JSONDecodeError:
            logger.debug("Request body is not valid JSON")
        except Exception as e:
            logger.warning("Failed to read request body: %s", e)

    return JSONResponse(
        {"status": "success", "message": "Events logged successfully"},
        status_code=200,
    )
