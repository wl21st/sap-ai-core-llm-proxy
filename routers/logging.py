"""Router for /api/event_logging/batch endpoint."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from utils.logging_utils import get_server_logger

logger = get_server_logger(__name__)

router = APIRouter()


@router.post("/api/event_logging/batch")
@router.options("/api/event_logging/batch")
async def handle_event_logging(request: Request) -> JSONResponse:
    """Dummy endpoint for Claude Code event logging to prevent 404 errors."""
    logger.info("Received request to /api/event_logging/batch")
    logger.debug("Request headers: %s", request.headers)
    logger.debug("Request body: %s", await request.json())
    return JSONResponse(
        {"status": "success", "message": "Events logged successfully"},
        status_code=200,
    )
