"""Circuit breaker for SSL/certificate recovery operations.

Prevents cascading failures when the network is unstable (e.g. WiFi flapping).
Each time _handle_certificate_recovery is called it invalidates the SDK session
and makes a fresh Bedrock call.  Under rapid repeated SSL failures this would
hammer the SAP AI Core endpoint with a flood of session rebuilds and retries.

The circuit breaker tracks consecutive recovery failures per model and opens
after a configurable threshold, rejecting subsequent recovery attempts with
CircuitBreakerOpenError (→ 503 Service Unavailable) until a cooldown period
has elapsed.

States
------
CLOSED   Normal operation.  Recovery attempts are forwarded and outcomes tracked.
OPEN     Too many consecutive failures.  Recovery attempts are rejected immediately
         without touching the server.  Transitions to HALF_OPEN after cooldown.
HALF_OPEN One probe attempt is allowed through.  Success → CLOSED; failure → OPEN.

Thread-safety
-------------
All state mutations are protected by a per-breaker threading.Lock so the breaker
is safe to use from concurrent request-handling threads.
"""

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from logging import Logger

from utils import logging_utils

logger: Logger = logging_utils.get_server_logger(__name__)

# ---------------------------------------------------------------------------
# Defaults (can be overridden per-breaker instance)
# ---------------------------------------------------------------------------
DEFAULT_FAILURE_THRESHOLD: int = 3  # consecutive failures before opening
DEFAULT_RECOVERY_TIMEOUT: float = 30.0  # seconds before attempting half-open probe
DEFAULT_SUCCESS_THRESHOLD: int = 1  # successes in HALF_OPEN needed to close


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpenError(Exception):
    """Raised when a call is blocked because the circuit is OPEN.

    Callers should treat this as a temporary service-unavailable condition
    and return HTTP 503 to the client without retrying.
    """

    def __init__(self, model: str, retry_after: float) -> None:
        self.model = model
        self.retry_after = retry_after  # seconds until half-open probe allowed
        super().__init__(
            f"Circuit breaker OPEN for model '{model}': "
            f"SSL recovery blocked for {retry_after:.1f}s more. "
            "The server will retry automatically once the cooldown elapses."
        )


@dataclass
class CircuitBreaker:
    """Per-model circuit breaker for SSL/certificate recovery operations.

    Args:
        model: Model name (used only for logging).
        failure_threshold: Consecutive failures before opening the circuit.
        recovery_timeout: Seconds to wait in OPEN state before probing.
        success_threshold: Consecutive successes in HALF_OPEN to close.
    """

    model: str
    failure_threshold: int = DEFAULT_FAILURE_THRESHOLD
    recovery_timeout: float = DEFAULT_RECOVERY_TIMEOUT
    success_threshold: int = DEFAULT_SUCCESS_THRESHOLD

    _state: CircuitState = field(default=CircuitState.CLOSED, init=False, repr=False)
    _failure_count: int = field(default=0, init=False, repr=False)
    _success_count: int = field(default=0, init=False, repr=False)
    _opened_at: float = field(default=0.0, init=False, repr=False)
    _lock: threading.Lock = field(
        default_factory=threading.Lock, init=False, repr=False
    )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def state(self) -> CircuitState:
        """Current circuit state (may transition OPEN→HALF_OPEN on read)."""
        with self._lock:
            return self._get_state_locked()

    def call(self, fn, *args, **kwargs):
        """Execute *fn* if the circuit allows it, tracking success/failure.

        Args:
            fn: Callable to protect.
            *args, **kwargs: Forwarded to fn.

        Returns:
            Whatever fn returns on success.

        Raises:
            CircuitBreakerOpenError: If the circuit is OPEN and the cooldown
                has not yet elapsed.
            Exception: Whatever fn raises (also recorded as a failure).
        """
        with self._lock:
            state = self._get_state_locked()

            if state == CircuitState.OPEN:
                retry_after = self._seconds_until_half_open()
                logger.warning(
                    "Circuit breaker OPEN for model '%s': blocking SSL recovery "
                    "(retry after %.1fs)",
                    self.model,
                    retry_after,
                )
                raise CircuitBreakerOpenError(self.model, retry_after)

            # CLOSED or HALF_OPEN — allow the call through
            if state == CircuitState.HALF_OPEN:
                logger.info(
                    "Circuit breaker HALF_OPEN for model '%s': allowing probe attempt",
                    self.model,
                )

        # Execute outside the lock to avoid holding it during I/O
        try:
            result = fn(*args, **kwargs)
        except Exception:
            self._on_failure()
            raise

        self._on_success()
        return result

    def reset(self) -> None:
        """Manually reset the circuit to CLOSED (for testing / operator use)."""
        with self._lock:
            self._transition_to_closed()
            logger.info("Circuit breaker manually reset for model '%s'", self.model)

    # ------------------------------------------------------------------
    # Internal helpers (must be called with _lock held where noted)
    # ------------------------------------------------------------------

    def _get_state_locked(self) -> CircuitState:
        """Return current state, promoting OPEN→HALF_OPEN when timeout elapsed."""
        if (
            self._state == CircuitState.OPEN
            and time.monotonic() - self._opened_at >= self.recovery_timeout
        ):
            logger.info(
                "Circuit breaker transitioning OPEN→HALF_OPEN for model '%s' "
                "(cooldown elapsed)",
                self.model,
            )
            self._state = CircuitState.HALF_OPEN
            self._success_count = 0
        return self._state

    def _seconds_until_half_open(self) -> float:
        elapsed = time.monotonic() - self._opened_at
        return max(0.0, self.recovery_timeout - elapsed)

    def _on_failure(self) -> None:
        with self._lock:
            self._success_count = 0
            if self._state == CircuitState.HALF_OPEN:
                logger.warning(
                    "Circuit breaker probe FAILED for model '%s': "
                    "re-opening circuit (cooldown %.0fs)",
                    self.model,
                    self.recovery_timeout,
                )
                self._transition_to_open()
            else:
                self._failure_count += 1
                logger.debug(
                    "Circuit breaker failure %d/%d for model '%s'",
                    self._failure_count,
                    self.failure_threshold,
                    self.model,
                )
                if self._failure_count >= self.failure_threshold:
                    logger.warning(
                        "Circuit breaker OPENING for model '%s' after %d consecutive "
                        "SSL recovery failures (cooldown %.0fs)",
                        self.model,
                        self._failure_count,
                        self.recovery_timeout,
                    )
                    self._transition_to_open()

    def _on_success(self) -> None:
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                logger.info(
                    "Circuit breaker probe SUCCEEDED for model '%s' (%d/%d)",
                    self.model,
                    self._success_count,
                    self.success_threshold,
                )
                if self._success_count >= self.success_threshold:
                    self._transition_to_closed()
            else:
                # CLOSED — reset failure counter on any success
                if self._failure_count > 0:
                    self._failure_count = 0

    def _transition_to_open(self) -> None:
        self._state = CircuitState.OPEN
        self._opened_at = time.monotonic()
        self._failure_count = 0

    def _transition_to_closed(self) -> None:
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0


# ---------------------------------------------------------------------------
# Process-wide registry — one breaker per model, created lazily
# ---------------------------------------------------------------------------

_registry_lock = threading.Lock()
_breaker_registry: dict[str, CircuitBreaker] = {}


def get_ssl_circuit_breaker(
    model: str,
    failure_threshold: int = DEFAULT_FAILURE_THRESHOLD,
    recovery_timeout: float = DEFAULT_RECOVERY_TIMEOUT,
) -> CircuitBreaker:
    """Return the singleton CircuitBreaker for *model*, creating it if needed.

    All keyword arguments are only used on first creation; subsequent calls for
    the same model return the existing breaker unchanged.
    """
    if model in _breaker_registry:
        return _breaker_registry[model]
    with _registry_lock:
        if model not in _breaker_registry:
            _breaker_registry[model] = CircuitBreaker(
                model=model,
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
            )
            logger.debug(
                "Created SSL circuit breaker for model '%s' "
                "(threshold=%d, timeout=%.0fs)",
                model,
                failure_threshold,
                recovery_timeout,
            )
    return _breaker_registry[model]
