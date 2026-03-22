"""
Status endpoints for proxy server health and info.

Provides:
- /health - Simple health check
- /stats - Metrics and uptime
- /info - Proxy configuration details
"""

from fastapi import APIRouter, Request
from typing import Dict, Any

router = APIRouter(tags=["status"])


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """
    Health check endpoint.

    Returns:
        JSON response with status 'ok' if server is running
    """
    return {"status": "ok"}


@router.get("/stats")
async def get_stats(request: Request) -> Dict[str, Any]:
    """
    Get proxy server statistics.

    Returns:
        - request_count: Total number of requests processed
        - uptime_seconds: Server uptime in seconds
        - requests_by_model: Breakdown by model
        - requests_by_endpoint: Breakdown by endpoint
    """
    try:
        metrics = request.app.state.metrics.get_metrics()
    except AttributeError:
        # Metrics not initialized yet
        metrics = {
            "request_count": 0,
            "uptime_seconds": 0,
            "requests_by_model": {},
            "requests_by_endpoint": {},
        }

    return {
        "status": "metrics",
        "request_count": metrics["request_count"],
        "uptime_seconds": metrics["uptime_seconds"],
        "requests_by_model": metrics["requests_by_model"],
        "requests_by_endpoint": metrics["requests_by_endpoint"],
    }


@router.get("/info")
async def get_info(request: Request) -> Dict[str, Any]:
    """
    Get proxy configuration details.

    Returns:
        - status: 'details'
        - subaccounts: List of configured subaccounts
        - default_model: Default model for requests
        - host: Server host
        - port: Server port
    """
    config = request.app.state.proxy_config
    subaccount_names = list(config.subaccounts.keys())
    models_available = set()
    for sub_config in config.subaccounts.values():
        models_available.update(sub_config.model_to_deployment_urls.keys())

    return {
        "status": "details",
        "subaccounts": subaccount_names,
        "subaccount_count": len(subaccount_names),
        "available_models": sorted(list(models_available)),
        "host": config.host,
        "port": config.port,
    }
