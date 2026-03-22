"""
Middleware for collecting request metrics.

Tracks request counts per endpoint and model.
"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect metrics on all requests."""

    async def dispatch(self, request: Request, call_next):
        """Track request and pass to next middleware."""
        # Increment total request count (metrics initialized in lifespan)
        try:
            metrics = request.app.state.metrics
            metrics.increment_request_count()

            # Track by endpoint
            path = request.url.path
            metrics.increment_endpoint_request(path)
        except AttributeError:
            # Metrics not yet initialized (may happen during test setup)
            pass

        response = await call_next(request)
        return response
