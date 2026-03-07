from utils import sdk_connection_poolfrom utils import sdk_connection_poolfrom utils import sdk_connection_poolfrom utils import sdk_connection_pool

# SDK Session Management Tests Specification

## Overview

This document provides detailed specifications for unit tests covering the SAP AI Core SDK session and client management functions in [`proxy_server.py`](../proxy_server.py):

- [`get_sapaicore_sdk_session()`](../proxy_server.py:41) - Lines 41-49
- [`get_sapaicore_sdk_client()`](../proxy_server.py:52) - Lines 52-63

These functions implement caching and thread-safe lazy initialization patterns to avoid expensive SDK object creation on every request.

## Functions Under Test

### 1. get_sapaicore_sdk_session()

**Location:** [`proxy_server.py:41-49`](../proxy_server.py:41)

**Purpose:** Lazily initialize and return a global SAP AI Core SDK Session with thread-safe caching.

**Implementation Details:**

```python
__sdk_session = None
_sdk_session_lock = threading.Lock()


def get_sapaicore_sdk_session() -> Session:
    """Lazily initialize and return a global SAP AI Core SDK Session."""
    global __sdk_session
    if _sdk_session is None:
        with _sdk_session_lock:
            if _sdk_session is None:
                logging.info("Initializing global SAP AI SDK Session")
                _sdk_session = Session()
    return _sdk_session
```

**Key Characteristics:**

- Uses double-checked locking pattern for thread safety
- Initializes session only once per process
- Logs initialization event
- Returns cached session on subsequent calls

### 2. get_sapaicore_sdk_client()

**Location:** [`proxy_server.py:52-63`](../proxy_server.py:52)

**Purpose:** Get or create a cached SAP AI Core (Bedrock) client for a specific model.

**Implementation Details:**

```python
_bedrock_clients: Dict[str, Any] = {}
_bedrock_clients_lock = threading.Lock()

def get_sapaicore_sdk_client(model_name: str):
    """Get or create a cached SAP AI Core (Bedrock) client for the given model."""
    client = _bedrock_clients.get(model_name)
    if client is not None:
        return client
    with _bedrock_clients_lock:
        client = _bedrock_clients.get(model_name)
        if client is None:
            logging.info(f"Creating SAP AI SDK client for model '{model_name}'")
            client = get_sapaicore_sdk_session().client(model_name=model_name)
            _bedrock_clients[model_name] = client
    return client
```

**Key Characteristics:**

- Uses double-checked locking pattern for thread safety
- Caches clients per model name
- Reuses the global session
- Logs client creation events
- Different models get different client instances

## Test File Structure

**File:** `tests/unit/test_sdk_session_management.py`

**Dependencies:**

```python
import pytest
import threading
from unittest.mock import Mock, patch, MagicMock
from gen_ai_hub.proxy.native.amazon.clients import Session
```

## Test Specifications

### Class: TestGetSAPAICoreSDKSession

Tests for the [`get_sapaicore_sdk_session()`](../proxy_server.py:41) function.

#### Test 1: test_session_initialization_on_first_call

**Purpose:** Verify session is initialized on first call

**Setup:**

- Reset `proxy_server._sdk_session` to `None`
- Mock `Session` class

**Actions:**

- Call `get_sapaicore_sdk_session()`

**Assertions:**

- `Session()` constructor called exactly once
- Returned session matches mock instance
- Global `_sdk_session` is set to mock instance

**Code:**

```python
def test_session_initialization_on_first_call(self):
    """Test that session is initialized on first call."""
    import proxy_server

    proxy_server._sdk_session = None

    with patch('proxy_server.Session') as mock_session_class:
        mock_session_instance = Mock(spec=Session)
        mock_session_class.return_value = mock_session_instance

        result = sdk_connection_pool.__get_sdk_session()

        mock_session_class.assert_called_once()
        assert result == mock_session_instance
        assert proxy_server._sdk_session == mock_session_instance
```

#### Test 2: test_session_reuse_on_subsequent_calls

**Purpose:** Verify session is reused, not recreated

**Setup:**

- Set `proxy_server._sdk_session` to a mock session
- Mock `Session` class

**Actions:**

- Call `get_sapaicore_sdk_session()` three times

**Assertions:**

- `Session()` constructor never called
- All three calls return the same cached instance

**Code:**

```python
def test_session_reuse_on_subsequent_calls(self):
    """Test that session is reused on subsequent calls."""
    import proxy_server

    mock_session = Mock(spec=Session)
    proxy_server._sdk_session = mock_session

    with patch('proxy_server.Session') as mock_session_class:
        result1 = proxy_server.get_sdk_session()
        result2 = proxy_server.get_sdk_session()
        result3 = proxy_server.get_sdk_session()

        mock_session_class.assert_not_called()
        assert result1 == mock_session
        assert result2 == mock_session
        assert result3 == mock_session
```

#### Test 3: test_session_thread_safety_double_checked_locking

**Purpose:** Verify thread-safe initialization prevents race conditions

**Setup:**

- Reset `proxy_server._sdk_session` to `None`
- Mock `Session` with call counter

**Actions:**

- Create 10 threads that simultaneously call `get_sapaicore_sdk_session()`
- Start all threads
- Wait for completion

**Assertions:**

- `Session()` constructor called exactly once (not 10 times)
- All 10 threads receive the same session instance

**Code:**

```python
def test_session_thread_safety_double_checked_locking(self):
    """Test thread-safe initialization using double-checked locking pattern."""
    import proxy_server

    proxy_server._sdk_session = None

    mock_session = Mock(spec=Session)
    call_count = 0

    def mock_session_constructor():
        nonlocal call_count
        call_count += 1
        return mock_session

    with patch('proxy_server.Session', side_effect=mock_session_constructor):
        results = []
        threads = []

        def get_session():
            result = proxy_server.get_sdk_session()
            results.append(result)

        for _ in range(10):
            thread = threading.Thread(target=get_session)
            threads.append(thread)

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        assert call_count == 1
        assert len(results) == 10
        assert all(r == mock_session for r in results)
```

#### Test 4: test_session_initialization_logs_message

**Purpose:** Verify logging occurs during initialization

**Setup:**

- Reset `proxy_server._sdk_session` to `None`
- Mock `Session` and `logging.info`

**Actions:**

- Call `get_sapaicore_sdk_session()`

**Assertions:**

- `logging.info` called with "Initializing global SAP AI SDK Session"

**Code:**

```python
def test_session_initialization_logs_message(self):
    """Test that session initialization logs an info message."""
    import proxy_server

    proxy_server._sdk_session = None

    with patch('proxy_server.Session') as mock_session_class,
            patch('proxy_server.logging.info') as mock_log_info:
        mock_session_class.return_value = Mock(spec=Session)

        proxy_server.get_sdk_session()

        mock_log_info.assert_called_with("Initializing global SAP AI SDK Session")
```

### Class: TestGetSAPAICoreSDKClient

Tests for the [`get_sapaicore_sdk_client()`](../proxy_server.py:52) function.

#### Test 5: test_client_creation_on_first_call_for_model

**Purpose:** Verify client is created on first call for a model

**Setup:**

- Reset `proxy_server._bedrock_clients` to `{}`
- Mock session with client factory

**Actions:**

- Call `get_sapaicore_sdk_client("claude-3-opus")`

**Assertions:**

- `session.client()` called with correct model name
- Returned client matches mock
- Client cached in `_bedrock_clients`

**Code:**

```python
def test_client_creation_on_first_call_for_model(self):
    """Test that client is created on first call for a specific model."""
    import proxy_server

    proxy_server._bedrock_clients = {}

    mock_session = Mock(spec=Session)
    mock_client = Mock()
    mock_session.client.return_value = mock_client

    with patch('proxy_server.get_sapaicore_sdk_session', return_value=mock_session):
        result = proxy_server.get_bedrock_client("claude-3-opus")

        mock_session.client.assert_called_once_with(model_name="claude-3-opus")
        assert result == mock_client
        assert proxy_server._bedrock_clients["claude-3-opus"] == mock_client
```

#### Test 6: test_client_reuse_for_same_model

**Purpose:** Verify client is reused for same model

**Setup:**

- Set `proxy_server._bedrock_clients` with cached client
- Mock session

**Actions:**

- Call `get_sapaicore_sdk_client("claude-3-opus")` twice

**Assertions:**

- `session.client()` never called
- Both calls return cached client

**Code:**

```python
def test_client_reuse_for_same_model(self):
    """Test that client is reused for subsequent calls with same model."""
    import proxy_server

    mock_client = Mock()
    proxy_server._bedrock_clients = {"claude-3-opus": mock_client}

    mock_session = Mock(spec=Session)

    with patch('proxy_server.get_sapaicore_sdk_session', return_value=mock_session):
        result1 = proxy_server.get_bedrock_client("claude-3-opus")
        result2 = proxy_server.get_bedrock_client("claude-3-opus")

        mock_session.client.assert_not_called()
        assert result1 == mock_client
        assert result2 == mock_client
```

#### Test 7: test_different_clients_for_different_models

**Purpose:** Verify different models get different clients

**Setup:**

- Reset `proxy_server._bedrock_clients` to `{}`
- Mock session with model-specific client factory

**Actions:**

- Call `get_sapaicore_sdk_client()` for two different models

**Assertions:**

- Two different client instances created
- Both cached separately
- Each model gets its own client

**Code:**

```python
def test_different_clients_for_different_models(self):
    """Test that different clients are created for different models."""
    import proxy_server

    proxy_server._bedrock_clients = {}

    mock_session = Mock(spec=Session)
    mock_client_opus = Mock()
    mock_client_sonnet = Mock()

    def mock_client_factory(model_name):
        if model_name == "claude-3-opus":
            return mock_client_opus
        elif model_name == "claude-3-sonnet":
            return mock_client_sonnet
        return Mock()

    mock_session.client.side_effect = mock_client_factory

    with patch('proxy_server.get_sapaicore_sdk_session', return_value=mock_session):
        result_opus = sdk_connection_pool.get_bedrock_client("claude-3-opus")
        result_sonnet = proxy_server.get_bedrock_client("claude-3-sonnet")

        assert result_opus == mock_client_opus
        assert result_sonnet == mock_client_sonnet
        assert result_opus != result_sonnet
        assert proxy_server._bedrock_clients["claude-3-opus"] == mock_client_opus
        assert proxy_server._bedrock_clients["claude-3-sonnet"] == mock_client_sonnet
```

#### Test 8: test_client_thread_safety_double_checked_locking

**Purpose:** Verify thread-safe client creation

**Setup:**

- Reset `proxy_server._bedrock_clients` to `{}`
- Mock session with call counter

**Actions:**

- Create 10 threads requesting same model simultaneously
- Start all threads
- Wait for completion

**Assertions:**

- Client created exactly once (not 10 times)
- All threads receive same client instance

**Code:**

```python
def test_client_thread_safety_double_checked_locking(self):
    """Test thread-safe client creation using double-checked locking."""
    import proxy_server

    proxy_server._bedrock_clients = {}

    mock_session = Mock(spec=Session)
    mock_client = Mock()
    client_creation_count = 0

    def mock_client_factory(model_name):
        nonlocal client_creation_count
        client_creation_count += 1
        return mock_client

    mock_session.client.side_effect = mock_client_factory

    with patch('proxy_server.get_sapaicore_sdk_session', return_value=mock_session):
        results = []
        threads = []

        def get_client():
            result = proxy_server.get_bedrock_client("claude-3-opus")
            results.append(result)

        for _ in range(10):
            thread = threading.Thread(target=get_client)
            threads.append(thread)

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        assert client_creation_count == 1
        assert len(results) == 10
        assert all(r == mock_client for r in results)
```

#### Test 9: test_client_creation_logs_message

**Purpose:** Verify logging occurs during client creation

**Setup:**

- Reset `proxy_server._bedrock_clients` to `{}`
- Mock session and `logging.info`

**Actions:**

- Call `get_sapaicore_sdk_client("claude-3-opus")`

**Assertions:**

- `logging.info` called with expected message including model name

**Code:**

```python
def test_client_creation_logs_message(self):
    """Test that client creation logs an info message."""
    import proxy_server

    proxy_server._bedrock_clients = {}

    mock_session = Mock(spec=Session)
    mock_client = Mock()
    mock_session.client.return_value = mock_client

    with patch('proxy_server.get_sapaicore_sdk_session', return_value=mock_session),
        patch('proxy_server.logging.info') as mock_log_info:
    proxy_server.get_bedrock_client("claude-3-opus")

    mock_log_info.assert_called_with(
        "Creating SAP AI SDK client for model 'claude-3-opus'"
    )
```

#### Test 10: test_client_cache_returns_none_check

**Purpose:** Verify None values in cache are handled correctly

**Setup:**

- Set `proxy_server._bedrock_clients` with `None` value (edge case)
- Mock session

**Actions:**

- Call `get_sapaicore_sdk_client()` for model with `None` cached

**Assertions:**

- New client created despite cache entry
- Cache updated with real client

**Code:**

```python
def test_client_cache_returns_none_check(self):
    """Test that None check works correctly for cache lookup."""
    import proxy_server

    proxy_server._bedrock_clients = {"test-model": None}

    mock_session = Mock(spec=Session)
    mock_client = Mock()
    mock_session.client.return_value = mock_client

    with patch('proxy_server.get_sapaicore_sdk_session', return_value=mock_session):
        result = proxy_server.get_bedrock_client("test-model")

        mock_session.client.assert_called_once_with(model_name="test-model")
        assert result == mock_client
```

### Class: TestSDKSessionAndClientIntegration

Integration tests for session and client working together.

#### Test 11: test_client_uses_session_correctly

**Purpose:** Verify client creation uses the global session

**Setup:**

- Reset both `_sdk_session` and `_bedrock_clients`
- Mock `Session` class

**Actions:**

- Call `get_sapaicore_sdk_client()`

**Assertions:**

- Session initialized
- Client created using that session
- Both cached correctly

**Code:**

```python
def test_client_uses_session_correctly(self):
    """Test that client creation uses the global session."""
    import proxy_server

    proxy_server._sdk_session = None
    proxy_server._bedrock_clients = {}

    mock_session = Mock(spec=Session)
    mock_client = Mock()
    mock_session.client.return_value = mock_client

    with patch('proxy_server.Session', return_value=mock_session):
        result = proxy_server.get_bedrock_client("claude-3-opus")

        assert proxy_server._sdk_session == mock_session
        mock_session.client.assert_called_once_with(model_name="claude-3-opus")
        assert result == mock_client
```

#### Test 12: test_multiple_clients_share_same_session

**Purpose:** Verify multiple clients share one session

**Setup:**

- Reset both caches
- Mock `Session` with client factory

**Actions:**

- Create clients for two different models

**Assertions:**

- Session initialized only once
- Both clients use same session
- Two different client instances created

**Code:**

```python
def test_multiple_clients_share_same_session(self):
    """Test that multiple clients share the same session instance."""
    import proxy_server

    proxy_server._sdk_session = None
    proxy_server._bedrock_clients = {}

    mock_session = Mock(spec=Session)
    mock_client1 = Mock()
    mock_client2 = Mock()

    def mock_client_factory(model_name):
        if model_name == "model1":
            return mock_client1
        return mock_client2

    mock_session.client.side_effect = mock_client_factory

    with patch('proxy_server.Session', return_value=mock_session) as mock_session_class:
        client1 = proxy_server.get_bedrock_client("model1")
        client2 = proxy_server.get_bedrock_client("model2")

        mock_session_class.assert_called_once()
        assert mock_session.client.call_count == 2
        assert client1 == mock_client1
        assert client2 == mock_client2
```

#### Test 13: test_concurrent_session_and_client_initialization

**Purpose:** Verify concurrent initialization of session and multiple clients

**Setup:**

- Reset both caches
- Mock with counters for session and clients

**Actions:**

- Create 15 threads requesting 3 different models (5 threads per model)
- Start all threads simultaneously
- Wait for completion

**Assertions:**

- Session initialized exactly once
- Each model's client created exactly once
- All threads receive correct results

**Code:**

```python
def test_concurrent_session_and_client_initialization(self):
    """Test concurrent initialization of session and multiple clients."""
    import proxy_server

    proxy_server._sdk_session = None
    proxy_server._bedrock_clients = {}

    mock_session = Mock(spec=Session)
    session_init_count = 0

    def mock_session_constructor():
        nonlocal session_init_count
        session_init_count += 1
        return mock_session

    client_creation_counts = {}

    def mock_client_factory(model_name):
        if model_name not in client_creation_counts:
            client_creation_counts[model_name] = 0
        client_creation_counts[model_name] += 1
        return Mock()

    mock_session.client.side_effect = mock_client_factory

    with patch('proxy_server.Session', side_effect=mock_session_constructor):
        results = []
        threads = []

        models = ["model1", "model2", "model3"] * 5  # 15 threads total

        def get_client(model_name):
            result = proxy_server.get_bedrock_client(model_name)
            results.append((model_name, result))

        for model in models:
            thread = threading.Thread(target=get_client, args=(model,))
            threads.append(thread)

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        assert session_init_count == 1
        assert client_creation_counts["model1"] == 1
        assert client_creation_counts["model2"] == 1
        assert client_creation_counts["model3"] == 1
        assert len(results) == 15
```

### Class: TestSDKCachePerformance

Performance-focused tests for caching behavior.

#### Test 14: test_session_cache_avoids_expensive_initialization

**Purpose:** Verify caching prevents repeated expensive operations

**Setup:**

- Reset session cache
- Mock `Session` with expensive initialization counter

**Actions:**

- Call `get_sapaicore_sdk_session()` 100 times

**Assertions:**

- Expensive initialization happens only once

**Code:**

```python
def test_session_cache_avoids_expensive_initialization(self):
    """Test that caching avoids expensive session initialization."""
    import proxy_server

    proxy_server._sdk_session = None

    expensive_init_count = 0

    def expensive_session_init():
        nonlocal expensive_init_count
        expensive_init_count += 1
        return Mock(spec=Session)

    with patch('proxy_server.Session', side_effect=expensive_session_init):
        for _ in range(100):
            proxy_server.get_sdk_session()

        assert expensive_init_count == 1
```

#### Test 15: test_client_cache_avoids_expensive_client_creation

**Purpose:** Verify client caching prevents repeated creation

**Setup:**

- Reset client cache
- Mock session with expensive client creation counter

**Actions:**

- Call `get_sapaicore_sdk_client()` 100 times for same model

**Assertions:**

- Expensive client creation happens only once

**Code:**

```python
def test_client_cache_avoids_expensive_client_creation(self):
    """Test that caching avoids expensive client creation."""
    import proxy_server

    proxy_server._bedrock_clients = {}

    mock_session = Mock(spec=Session)
    client_creation_count = 0

    def expensive_client_creation(model_name):
        nonlocal client_creation_count
        client_creation_count += 1
        return Mock()

    mock_session.client.side_effect = expensive_client_creation

    with patch('proxy_server.get_sapaicore_sdk_session', return_value=mock_session):
        for _ in range(100):
            proxy_server.get_bedrock_client("claude-3-opus")

        assert client_creation_count == 1
```

## Test Coverage Summary

### Functions Covered

- ✅ [`get_sapaicore_sdk_session()`](../proxy_server.py:41) - 100% coverage
- ✅ [`get_sapaicore_sdk_client()`](../proxy_server.py:52) - 100% coverage

### Test Categories

- **Initialization Tests:** 4 tests
- **Caching Tests:** 4 tests
- **Thread Safety Tests:** 3 tests
- **Integration Tests:** 3 tests
- **Performance Tests:** 2 tests

**Total:** 15 comprehensive test cases

### Coverage Metrics

- **Line Coverage:** 100% of both functions
- **Branch Coverage:** All conditional branches tested
- **Concurrency Coverage:** Thread-safety verified with concurrent tests
- **Edge Cases:** None values, multiple models, repeated calls

## Implementation Notes

### Test Isolation

Each test should:

1. Reset global state (`_sdk_session`, `_bedrock_clients`)
2. Use mocks to avoid real SDK initialization
3. Clean up after execution

### Mock Strategy

- Mock `Session` class for session tests
- Mock `get_sapaicore_sdk_session()` for client tests
- Use `side_effect` for counters and conditional behavior

### Thread Safety Testing

- Use `threading.Thread` for concurrent tests
- Verify initialization happens exactly once
- Confirm all threads receive same cached instance

### Performance Testing

- Use loop counters to verify caching effectiveness
- Simulate expensive operations with counters
- Verify operations happen only once despite many calls

## Running the Tests

```bash
# Run all SDK session management tests
pytest tests/unit/test_sdk_session_management.py -v

# Run specific test class
pytest tests/unit/test_sdk_session_management.py::TestGetSAPAICoreSDKSession -v

# Run with coverage
pytest tests/unit/test_sdk_session_management.py --cov=proxy_server --cov-report=term-missing

# Run thread safety tests only
pytest tests/unit/test_sdk_session_management.py -k "thread_safety" -v
```

## Expected Results

All 15 tests should pass, demonstrating:

- ✅ Correct lazy initialization
- ✅ Effective caching behavior
- ✅ Thread-safe concurrent access
- ✅ Proper logging
- ✅ Integration between session and clients
- ✅ Performance optimization through caching

## Integration with CI/CD

These tests should be:

- Run on every commit
- Required to pass before merge
- Included in coverage reports
- Fast enough for frequent execution (< 5 seconds)

---

**Document Version:** 1.0  
**Last Updated:** 2025-12-15  
**Author:** Kilo Code (Architect Mode)
