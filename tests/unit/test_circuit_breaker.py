"""Unit tests for utils/circuit_breaker.py.

Covers:
- State transitions: CLOSED → OPEN → HALF_OPEN → CLOSED
- CircuitBreakerOpenError raised when OPEN
- Retry-after value exposed on the error
- Success resets failure counter in CLOSED state
- Half-open probe failure re-opens the circuit
- Half-open probe success closes the circuit
- get_ssl_circuit_breaker registry (singleton per model)
- Manual reset()
- Thread-safety smoke test
"""

import threading
import time

import pytest

from utils.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitState,
    get_ssl_circuit_breaker,
    _breaker_registry,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_breaker(threshold: int = 3, timeout: float = 30.0) -> CircuitBreaker:
    return CircuitBreaker(
        model="test-model", failure_threshold=threshold, recovery_timeout=timeout
    )


def failing_fn():
    raise RuntimeError("boom")


def success_fn():
    return "ok"


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------


class TestInitialState:
    def test_starts_closed(self):
        cb = make_breaker()
        assert cb.state == CircuitState.CLOSED

    def test_failure_count_starts_zero(self):
        cb = make_breaker()
        assert cb._failure_count == 0


# ---------------------------------------------------------------------------
# CLOSED → OPEN transition
# ---------------------------------------------------------------------------


class TestClosedToOpen:
    def test_opens_after_threshold_failures(self):
        cb = make_breaker(threshold=3)
        for _ in range(3):
            with pytest.raises(RuntimeError):
                cb.call(failing_fn)
        assert cb.state == CircuitState.OPEN

    def test_does_not_open_before_threshold(self):
        cb = make_breaker(threshold=3)
        for _ in range(2):
            with pytest.raises(RuntimeError):
                cb.call(failing_fn)
        assert cb.state == CircuitState.CLOSED

    def test_success_resets_failure_counter(self):
        cb = make_breaker(threshold=3)
        with pytest.raises(RuntimeError):
            cb.call(failing_fn)
        with pytest.raises(RuntimeError):
            cb.call(failing_fn)
        cb.call(success_fn)  # success should reset counter
        # Two more failures should NOT open (counter was reset)
        with pytest.raises(RuntimeError):
            cb.call(failing_fn)
        with pytest.raises(RuntimeError):
            cb.call(failing_fn)
        assert cb.state == CircuitState.CLOSED

    def test_open_raises_circuit_breaker_error(self):
        cb = make_breaker(threshold=2)
        for _ in range(2):
            with pytest.raises(RuntimeError):
                cb.call(failing_fn)
        with pytest.raises(CircuitBreakerOpenError):
            cb.call(success_fn)

    def test_open_error_contains_retry_after(self):
        cb = make_breaker(threshold=1, timeout=45.0)
        with pytest.raises(RuntimeError):
            cb.call(failing_fn)
        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            cb.call(success_fn)
        # retry_after should be close to 45s (within a small margin)
        assert 40.0 <= exc_info.value.retry_after <= 45.1

    def test_open_error_references_model(self):
        cb = CircuitBreaker(model="my-model", failure_threshold=1)
        with pytest.raises(RuntimeError):
            cb.call(failing_fn)
        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            cb.call(success_fn)
        assert "my-model" in str(exc_info.value)


# ---------------------------------------------------------------------------
# OPEN → HALF_OPEN transition (time-based)
# ---------------------------------------------------------------------------


class TestOpenToHalfOpen:
    def test_transitions_to_half_open_after_timeout(self):
        cb = make_breaker(threshold=1, timeout=0.05)
        with pytest.raises(RuntimeError):
            cb.call(failing_fn)
        assert cb.state == CircuitState.OPEN
        time.sleep(0.1)
        assert cb.state == CircuitState.HALF_OPEN

    def test_does_not_transition_before_timeout(self):
        cb = make_breaker(threshold=1, timeout=60.0)
        with pytest.raises(RuntimeError):
            cb.call(failing_fn)
        assert cb.state == CircuitState.OPEN
        # Immediately check — should still be OPEN
        assert cb.state == CircuitState.OPEN


# ---------------------------------------------------------------------------
# HALF_OPEN behaviour
# ---------------------------------------------------------------------------


class TestHalfOpen:
    def test_probe_success_closes_circuit(self):
        cb = make_breaker(threshold=1, timeout=0.05)
        with pytest.raises(RuntimeError):
            cb.call(failing_fn)
        time.sleep(0.1)
        assert cb.state == CircuitState.HALF_OPEN
        result = cb.call(success_fn)
        assert result == "ok"
        assert cb.state == CircuitState.CLOSED

    def test_probe_failure_reopens_circuit(self):
        cb = make_breaker(threshold=1, timeout=0.05)
        with pytest.raises(RuntimeError):
            cb.call(failing_fn)
        time.sleep(0.1)
        assert cb.state == CircuitState.HALF_OPEN
        with pytest.raises(RuntimeError):
            cb.call(failing_fn)
        assert cb.state == CircuitState.OPEN

    def test_probe_failure_resets_opened_at_for_new_cooldown(self):
        cb = make_breaker(threshold=1, timeout=0.1)
        with pytest.raises(RuntimeError):
            cb.call(failing_fn)
        time.sleep(0.15)
        # half-open probe fails
        with pytest.raises(RuntimeError):
            cb.call(failing_fn)
        # Circuit re-opened — should still be OPEN immediately after
        assert cb.state == CircuitState.OPEN

    def test_closed_after_probe_success_resets_counters(self):
        cb = make_breaker(threshold=2, timeout=0.05)
        # Trigger two failures → OPEN
        for _ in range(2):
            with pytest.raises(RuntimeError):
                cb.call(failing_fn)
        time.sleep(0.1)
        # Probe succeeds → CLOSED
        cb.call(success_fn)
        assert cb.state == CircuitState.CLOSED
        assert cb._failure_count == 0
        assert cb._success_count == 0


# ---------------------------------------------------------------------------
# Manual reset
# ---------------------------------------------------------------------------


class TestManualReset:
    def test_reset_closes_open_circuit(self):
        cb = make_breaker(threshold=1)
        with pytest.raises(RuntimeError):
            cb.call(failing_fn)
        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED

    def test_reset_allows_calls_again(self):
        cb = make_breaker(threshold=1)
        with pytest.raises(RuntimeError):
            cb.call(failing_fn)
        cb.reset()
        result = cb.call(success_fn)
        assert result == "ok"

    def test_reset_clears_failure_count(self):
        cb = make_breaker(threshold=5)
        for _ in range(4):
            with pytest.raises(RuntimeError):
                cb.call(failing_fn)
        cb.reset()
        assert cb._failure_count == 0


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class TestRegistry:
    def setup_method(self):
        # Clean up registry entries created by this test
        self._keys_to_clean = []

    def teardown_method(self):
        for k in self._keys_to_clean:
            _breaker_registry.pop(k, None)

    def test_returns_same_instance_for_same_model(self):
        key = "__test_registry_same__"
        self._keys_to_clean.append(key)
        a = get_ssl_circuit_breaker(key)
        b = get_ssl_circuit_breaker(key)
        assert a is b

    def test_returns_different_instances_for_different_models(self):
        key1, key2 = "__test_reg_a__", "__test_reg_b__"
        self._keys_to_clean += [key1, key2]
        a = get_ssl_circuit_breaker(key1)
        b = get_ssl_circuit_breaker(key2)
        assert a is not b

    def test_state_persists_across_registry_lookups(self):
        key = "__test_registry_state__"
        self._keys_to_clean.append(key)
        cb = get_ssl_circuit_breaker(key, failure_threshold=1)
        with pytest.raises(RuntimeError):
            cb.call(failing_fn)
        cb2 = get_ssl_circuit_breaker(key)
        assert cb2.state == CircuitState.OPEN


# ---------------------------------------------------------------------------
# Thread-safety smoke test
# ---------------------------------------------------------------------------


class TestThreadSafety:
    def test_concurrent_failures_open_circuit_exactly_once(self):
        cb = make_breaker(threshold=5, timeout=60.0)
        errors = []

        def worker():
            try:
                cb.call(failing_fn)
            except (RuntimeError, CircuitBreakerOpenError) as exc:
                errors.append(type(exc).__name__)

        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Eventually the circuit should be open
        assert cb.state == CircuitState.OPEN
        # Some calls got RuntimeError (before threshold), rest got CircuitBreakerOpenError
        assert "RuntimeError" in errors
        assert "CircuitBreakerOpenError" in errors
