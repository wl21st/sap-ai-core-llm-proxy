"""
Metrics tracking for SAP AI Core LLM Proxy.

Provides thread-safe request counting and uptime tracking.
"""

import threading
import time
from typing import Dict


class MetricsCollector:
    """Thread-safe metrics collection for the proxy server."""

    def __init__(self):
        self._lock = threading.Lock()
        self._request_count = 0
        self._start_time = time.time()
        self._requests_by_model: Dict[str, int] = {}
        self._requests_by_endpoint: Dict[str, int] = {}

    def increment_request_count(self) -> None:
        """Increment the total request counter."""
        with self._lock:
            self._request_count += 1

    def increment_model_request(self, model: str) -> None:
        """Increment request count for a specific model."""
        with self._lock:
            self._requests_by_model[model] = self._requests_by_model.get(model, 0) + 1

    def increment_endpoint_request(self, endpoint: str) -> None:
        """Increment request count for a specific endpoint."""
        with self._lock:
            self._requests_by_endpoint[endpoint] = (
                self._requests_by_endpoint.get(endpoint, 0) + 1
            )

    def get_metrics(self) -> Dict:
        """Get current metrics snapshot."""
        with self._lock:
            uptime_seconds = int(time.time() - self._start_time)
            return {
                "request_count": self._request_count,
                "uptime_seconds": uptime_seconds,
                "requests_by_model": dict(self._requests_by_model),
                "requests_by_endpoint": dict(self._requests_by_endpoint),
            }

    def get_request_count(self) -> int:
        """Get total request count."""
        with self._lock:
            return self._request_count

    def get_uptime_seconds(self) -> int:
        """Get uptime in seconds."""
        return int(time.time() - self._start_time)
