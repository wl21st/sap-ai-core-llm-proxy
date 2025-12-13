# Test Suite for SAP AI Core LLM Proxy

This directory contains comprehensive tests for the `proxy_server.py` module.

## Test Structure

```
tests/
├── __init__.py              # Test package initialization
├── test_proxy_server.py     # Main test suite
└── README.md               # This file
```

## Test Coverage

The test suite covers the following components:

### 1. **Dataclasses** (`TestServiceKey`, `TestTokenInfo`, `TestSubAccountConfig`, `TestProxyConfig`)

- ServiceKey creation and validation
- TokenInfo default values and threading locks
- SubAccountConfig initialization and service key loading
- ProxyConfig model mapping and initialization

### 2. **Utility Functions** (`TestModelDetection`, `TestConversionFunctions`)

- Model detection (Claude, Gemini, Claude 3.7/4)
- Payload conversion between OpenAI, Claude, and Gemini formats
- Response conversion for different model types
- HTTP 429 error handling

### 3. **Token Management** (`TestTokenManagement`)

- Token verification with various header formats
- Token fetching with caching
- Token expiry handling
- Multi-subaccount token management

### 4. **Load Balancing** (`TestLoadBalancing`)

- Round-robin load balancing across subaccounts
- Model fallback mechanisms
- URL selection for multiple deployments
- Error handling for missing models

### 5. **Flask Endpoints** (`TestFlaskEndpoints`)

- `/v1/models` - Model listing
- `/v1/chat/completions` - Chat completions
- `/v1/messages` - Claude Messages API
- `/v1/embeddings` - Embeddings API
- `/api/event_logging/batch` - Event logging

### 6. **Integration Tests** (`TestIntegration`)

- Complete request/response workflows
- Multi-component interaction testing
- End-to-end API flows

## Running Tests

### Install Test Dependencies

```bash
# Using uv (recommended)
uv sync --extra dev

# Or using pip
pip install -e ".[dev]"
```

### Run All Tests

```bash
# Using make
make test

# Or directly with pytest
pytest

# Or with uv
uv run pytest
```

### Run Specific Test Classes

```bash
# Run only dataclass tests
pytest tests/test_proxy_server.py::TestServiceKey

# Run only utility function tests
pytest tests/test_proxy_server.py::TestModelDetection
```

### Run Specific Test Methods

```bash
# Run a single test
pytest tests/test_proxy_server.py::TestTokenManagement::test_verify_request_token_valid
```

### Run with Coverage

```bash
# Generate coverage report
pytest --cov=proxy_server --cov-report=html

# View coverage report
open htmlcov/index.html
```

### Run with Verbose Output

```bash
pytest -v
```

### Run Tests Matching a Pattern

```bash
# Run all tests with "token" in the name
pytest -k token

# Run all tests with "claude" in the name
pytest -k claude
```

## Test Markers

Tests are organized with markers for selective execution:

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Run only slow tests
pytest -m slow

# Skip slow tests
pytest -m "not slow"
```

## Writing New Tests

### Test Structure

Follow this structure for new tests:

```python
class TestNewFeature:
    """Tests for new feature."""
    
    def test_basic_functionality(self):
        """Test basic functionality."""
        # Arrange
        input_data = {"key": "value"}
        
        # Act
        result = function_under_test(input_data)
        
        # Assert
        assert result == expected_output
    
    @pytest.mark.parametrize("input,expected", [
        ("input1", "output1"),
        ("input2", "output2"),
    ])
    def test_with_parameters(self, input, expected):
        """Test with multiple parameter sets."""
        assert function_under_test(input) == expected
```

### Using Fixtures

```python
@pytest.fixture
def sample_data():
    """Provide sample data for tests."""
    return {"key": "value"}

def test_with_fixture(sample_data):
    """Test using fixture."""
    assert sample_data["key"] == "value"
```

### Mocking External Dependencies

```python
@patch('proxy_server.requests.post')
def test_with_mock(mock_post):
    """Test with mocked HTTP request."""
    mock_response = Mock()
    mock_response.json.return_value = {"result": "success"}
    mock_post.return_value = mock_response
    
    result = function_that_makes_request()
    
    assert result["result"] == "success"
    mock_post.assert_called_once()
```

## Test Best Practices

1. **Isolation**: Each test should be independent and not rely on other tests
2. **Clarity**: Test names should clearly describe what is being tested
3. **Arrange-Act-Assert**: Follow the AAA pattern for test structure
4. **Mocking**: Mock external dependencies (HTTP requests, file I/O, etc.)
5. **Fixtures**: Use fixtures for common test data and setup
6. **Parametrization**: Use `@pytest.mark.parametrize` for testing multiple inputs
7. **Coverage**: Aim for high code coverage but focus on meaningful tests
8. **Documentation**: Add docstrings to test classes and methods

## Continuous Integration

Tests are automatically run in CI/CD pipelines. Ensure all tests pass before submitting pull requests.

## Troubleshooting

### Import Errors

If you encounter import errors:

```bash
# Ensure the package is installed in development mode
uv sync --extra dev

# Or
pip install -e ".[dev]"
```

### Fixture Not Found

Ensure fixtures are defined in the same file or in `conftest.py`:

```python
# conftest.py
import pytest

@pytest.fixture
def shared_fixture():
    return "shared data"
```

### Mock Not Working

Ensure you're patching the correct import path:

```python
# Patch where the function is used, not where it's defined
@patch('proxy_server.requests.post')  # Correct
# Not: @patch('requests.post')
```

## Additional Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Pytest-cov Documentation](https://pytest-cov.readthedocs.io/)
- [Python unittest.mock Documentation](https://docs.python.org/3/library/unittest.mock.html)
