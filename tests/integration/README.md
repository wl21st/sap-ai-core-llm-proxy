# Real Integration Tests

This directory contains real integration tests that run against an actual proxy server instance (typically localhost). These tests validate end-to-end functionality including model listing, chat completions, streaming, and the Claude Messages API.

## 🚀 Quick Start

```bash
# Run all integration tests (recommended)
make test-integration

# With enhanced request/response logging
uv run pytest tests/integration/ -m real -v --log-cli-level=INFO

# Quick smoke test
make test-integration-smoke
```

## Overview

The integration tests are designed to:
- Test against a running proxy server (not mocked)
- Validate all 5 required models: `anthropic--claude-4.5-sonnet`, `sonnet-4.5`, `gpt-4.1`, `gpt-5`, `gemini-2.5-pro`
- Test both streaming and non-streaming modes
- Validate token usage, SSE format, and response formats
- Provide smoke tests for quick validation
- **Enhanced logging** shows detailed request/response with timing information

## Test Structure

```
tests/integration/
├── __init__.py                    # Package initialization
├── conftest.py                    # Pytest fixtures and configuration
├── validators.py                  # Response validation utilities
├── test_config.json.example       # Example test configuration
├── test_models_endpoint.py        # /v1/models endpoint tests
├── test_chat_completions.py       # /v1/chat/completions tests
├── test_messages_endpoint.py      # /v1/messages tests (Claude)
└── README.md                      # This file
```

## Configuration

### Option 1: Configuration File

Create [`test_config.json`](test_config.json) (copy from [`test_config.json.example`](test_config.json.example)):

```json
{
  "proxy_url": "http://127.0.0.1:3001",
  "auth_token": "${PROXY_AUTH_TOKEN}",
  "models_to_test": [
    "anthropic--claude-4.5-sonnet",
    "sonnet-4.5",
    "gpt-4.1",
    "gpt-5",
    "gemini-2.5-pro"
  ],
  "test_prompts": {
    "simple": "Hello, how are you?",
    "math": "What is 2+2?",
    "creative": "Tell me a joke.",
    "technical": "Explain Python in one sentence."
  },
  "timeout": 30,
  "max_tokens": 100,
  "skip_if_server_not_running": true
}
```

### Option 2: Environment Variables

Set environment variables:

```bash
export PROXY_URL="http://127.0.0.1:3001"
export PROXY_AUTH_TOKEN="your-token-here"
export SKIP_INTEGRATION_TESTS="false"
```

## Prerequisites

1. **Install dependencies**:
   ```bash
   # Using uv (recommended)
   uv sync
   
   # Or install test dependencies specifically
   make install-test-deps
   ```

2. **Start the proxy server**:
   ```bash
   # Using uv
   uv run python proxy_server.py --config config.json
   
   # Or directly
   python proxy_server.py --config config.json
   ```

3. **Ensure you have valid authentication token** in your config or environment

4. **Verify server is running**:
   ```bash
   curl http://127.0.0.1:3001/v1/models
   ```

## Debug Logging

### Enable Debug Logging for Tests

To enable debug logging during test execution, use one of these methods:

**Method 1: Command-line flag** (recommended for one-time debugging):
```bash
# Enable console debug output
pytest tests/integration/ --log-cli-level=DEBUG -v

# Or using uv
uv run pytest tests/integration/ --log-cli-level=DEBUG -v
```

**Method 2: Enable console logging in pytest.ini**:
Edit [`pytest.ini`](../../pytest.ini) and change:
```ini
log_cli = true  # Change from false to true
log_cli_level = DEBUG  # Change from INFO to DEBUG
```

**Method 3: View debug logs in file**:
Debug logs are always written to `logs/pytest.log` regardless of console settings:
```bash
# Run tests
pytest tests/integration/ -v

# View debug logs
tail -f logs/pytest.log
```

**Method 4: Enable debug logging in proxy server**:
When starting the proxy server for integration tests:
```bash
# Start with debug flag
python proxy_server.py --config config.json --debug

# Or using uv
uv run python proxy_server.py --config config.json --debug
```

### Debug Logging Configuration

The logging configuration in [`pytest.ini`](../../pytest.ini) includes:

- **Console logging**: Controlled by `log_cli` and `log_cli_level`
- **File logging**: Always enabled at DEBUG level in `logs/pytest.log`
- **Format**: Timestamp, log level, logger name, and message
- **Proxy server**: Use `--debug` flag for detailed server logs

### Example: Full Debug Session

```bash
# Terminal 1: Start proxy server with debug logging
python proxy_server.py --config config.json --debug

# Terminal 2: Run tests with debug console output
pytest tests/integration/ --log-cli-level=DEBUG -v

# Or view file logs after running tests
pytest tests/integration/ -v
tail -f logs/pytest.log
```

## Running Tests

### 🚀 Quick Start: Run All Integration Tests

**Recommended Method (Make)**:
```bash
make test-integration
```

**UV Method**:
```bash
uv run pytest tests/integration/ -m real -v
```

**With Enhanced Logging**:
```bash
uv run pytest tests/integration/ -m real -v --log-cli-level=INFO
```

### 📋 What Gets Tested

The integration tests validate all **5 required models**:
- `anthropic--claude-4.5-sonnet`
- `sonnet-4.5`
- `gpt-4.1`
- `gpt-5`
- `gemini-2.5-pro`

**And all major endpoints**:
- `/v1/models` (model listing)
- `/v1/chat/completions` (streaming & non-streaming)
- `/v1/messages` (Claude-specific API)

### 🔍 Enhanced Request/Response Logging

All integration tests feature **enhanced logging** that shows:
- 🔵 **HTTP REQUEST**: Method, URL, headers, JSON body
- 🟢 **HTTP RESPONSE**: Status, timing, headers, response body
- ⏱️ **Response time tracking** for performance analysis
- 🔒 **Security**: Authorization headers automatically masked

**Example output**:
```
🔵🔵🔵 HTTP REQUEST START 🔵🔵🔵
📡 METHOD: POST
🌐 URL: http://127.0.0.1:3001/v1/chat/completions
📋 HEADERS:
   Authorization: ***
📦 JSON BODY:
{
  "model": "gpt-4.1",
  "messages": [{"role": "user", "content": "Hello"}]
}
🔵🔵🔵 HTTP REQUEST END 🔵🔵🔵

🟢🟢🟢 HTTP RESPONSE START 🟢🟢🟢
📊 STATUS: 200 OK
⏱️  RESPONSE TIME: 1.212s
📦 RESPONSE BODY:
{
  "choices": [{"message": {"content": "Hello! I'm here to help..."}}]
}
🟢🟢🟢 HTTP RESPONSE END 🟢🟢🟢
```

### 🎯 Running Specific Tests

#### Run All Tests for a Specific Model
```bash
# All tests for gpt-5
uv run pytest tests/integration/ -k "gpt-5" -v

# Using make
make test-integration-model MODEL=gpt-5
```

#### Run Specific Test Categories
```bash
# Smoke tests only (quick validation)
make test-integration-smoke
uv run pytest tests/integration/ -m "real and smoke" -v

# Streaming tests only
make test-integration-streaming
uv run pytest tests/integration/ -m "real and streaming" -v

# Non-streaming tests only
uv run pytest tests/integration/ -m "real and not streaming" -v
```

#### Run Specific Test Method
```bash
# Single test for specific model
uv run pytest "tests/integration/test_chat_completions.py::TestChatCompletionsNonStreaming::test_simple_completion[gpt-5]" -v

# With request/response logging
uv run pytest "tests/integration/test_chat_completions.py::TestChatCompletionsNonStreaming::test_simple_completion[gpt-5]" -v --log-cli-level=INFO
```

#### Run Specific Test Classes
```bash
# All non-streaming tests
uv run pytest tests/integration/test_chat_completions.py::TestChatCompletionsNonStreaming -v

# All streaming tests
uv run pytest tests/integration/test_chat_completions.py::TestChatCompletionsStreaming -v

# Models endpoint only
uv run pytest tests/integration/test_models_endpoint.py -v

# Claude Messages API only
uv run pytest tests/integration/test_messages_endpoint.py -v
```

### 🛠️ Running by Model Type

```bash
# Claude models only
uv run pytest tests/integration/ -m "real and claude" -v

# GPT models only
uv run pytest tests/integration/ -m "real and openai" -v

# Gemini models only
uv run pytest tests/integration/ -m "real and gemini" -v
```

### 📊 Test Execution Examples

**Full Test Suite with Debug Logging**:
```bash
# Make method
make test-integration

# UV method with INFO level (shows request/response)
uv run pytest tests/integration/ -m real -v --log-cli-level=INFO

# UV method with DEBUG level (maximum detail)
uv run pytest tests/integration/ -m real -v --log-cli-level=DEBUG
```

**Quick Validation**:
```bash
# Smoke tests (fastest)
make test-integration-smoke

# Or with UV
uv run pytest tests/integration/ -m "real and smoke" -v --log-cli-level=INFO
```

**Performance Testing**:
```bash
# All streaming tests to check real-time performance
make test-integration-streaming

# Check response times for specific model
uv run pytest tests/integration/ -k "gpt-5 and streaming" -v --log-cli-level=INFO
```

### Run Specific Test Categories

**Models endpoint only**:
```bash
# Using uv
uv run pytest tests/integration/test_models_endpoint.py -v

# Using pytest
pytest tests/integration/test_models_endpoint.py -v
```

**Chat completions (non-streaming)**:
```bash
uv run pytest tests/integration/test_chat_completions.py::TestChatCompletionsNonStreaming -v
```

**Chat completions (streaming)**:
```bash
uv run pytest tests/integration/test_chat_completions.py::TestChatCompletionsStreaming -v
```

**Claude Messages API**:
```bash
uv run pytest tests/integration/test_messages_endpoint.py -v
```

### Run by Model

**Claude models only**:
```bash
uv run pytest tests/integration/ -m "real and claude" -v
```

**Specific model**:
```bash
# Using make
make test-integration-model MODEL=sonnet-4.5

# Using uv
uv run pytest tests/integration/ -k "sonnet-4.5" -v
```

### Run by Test Type

**Smoke tests only** (quick validation):
```bash
# Using make
make test-integration-smoke

# Using uv
uv run pytest tests/integration/ -m "real and smoke" -v
```

**Streaming tests only**:
```bash
# Using make
make test-integration-streaming

# Using uv
uv run pytest tests/integration/ -m "real and streaming" -v
```

**Non-streaming tests only**:
```bash
uv run pytest tests/integration/ -m "real and not streaming" -v
```

### Skip if Server Not Running

By default, tests will skip if the server is not running (based on `skip_if_server_not_running` config). To fail instead:

```bash
# Edit test_config.json
{
  "skip_if_server_not_running": false
}
```

## Test Markers

The following pytest markers are available:

- `@pytest.mark.real` - Real integration tests against localhost
- `@pytest.mark.smoke` - Quick smoke tests
- `@pytest.mark.streaming` - Streaming response tests
- `@pytest.mark.claude` - Claude-specific tests
- `@pytest.mark.openai` - OpenAI-compatible tests
- `@pytest.mark.gemini` - Gemini-specific tests

## Test Coverage

### /v1/models Endpoint

- ✅ Returns 200 OK
- ✅ OpenAI-compatible response format
- ✅ Contains all required models
- ✅ Model metadata validation

### /v1/chat/completions Endpoint

**Non-Streaming Tests** (all 5 models):
- ✅ Simple completion
- ✅ Token usage validation
- ✅ Response format validation
- ✅ Common attributes validation
- ✅ Multiple messages support

**Streaming Tests** (all 5 models):
- ✅ Streaming completion
- ✅ SSE format validation
- ✅ Chunk structure validation
- ✅ Token usage in final chunk
- ✅ [DONE] signal validation

**Smoke Tests** (all 5 models):
- ✅ Simple prompt test
- ✅ Streaming smoke test

### /v1/messages Endpoint

**Claude Models** (`anthropic--claude-4.5-sonnet`, `sonnet-4.5`):
- ✅ Non-streaming messages
- ✅ Streaming messages
- ✅ Anthropic response format
- ✅ Token usage validation
- ✅ SSE format for streaming
- ✅ System prompt support
- ✅ Multiple conversation turns

**Non-Claude Models**:
- ✅ Fallback behavior validation

## Validation

The tests use [`ResponseValidator`](test_validators.py) class to validate:

### Token Usage
```python
validator.validate_token_usage(response_data)
```
- Checks `prompt_tokens`, `completion_tokens`, `total_tokens`
- Validates token counts are non-negative integers
- Verifies `total_tokens = prompt_tokens + completion_tokens`

### SSE Format

```python
validator.validate_sse_data_chunk(chunk_bytes)
```
- Validates SSE message starts with ``
- Checks for valid JSON or [DONE] signal
- Ensures proper format

### OpenAI Format
```python
validator.validate_openai_format(response_data)
```
- Validates required fields: `id`, `object`, `created`, `model`, `choices`
- Checks `object == "chat.completion"`
- Validates choice structure with `message` and `finish_reason`

### Claude Format
```python
validator.validate_claude_format(response_data)
```
- Validates required fields: `id`, `type`, `role`, `content`, `model`, `stop_reason`, `usage`
- Checks `type == "message"` and `role == "assistant"`
- Validates content structure

### Common Attributes
```python
validator.validate_common_attributes(response_data)
```
- Validates `id` and `model` fields are present and non-empty

## Request/Response Logging

All integration tests now automatically log HTTP requests and responses. The [`LoggingSession`](conftest.py:126) class in [`conftest.py`](conftest.py) intercepts all HTTP calls and logs:

- Request method, URL, headers, and body
- Response status code, headers, and body
- Formatted JSON for easy reading

**To see request/response logs**:

```bash
# Console output (INFO level shows requests/responses)
pytest tests/integration/test_chat_completions.py::TestChatCompletionsNonStreaming::test_simple_completion[gpt-5] -v --log-cli-level=INFO

# File output (always logged to logs/pytest.log)
pytest tests/integration/test_chat_completions.py::TestChatCompletionsNonStreaming::test_simple_completion[gpt-5] -v
tail -f logs/pytest.log
```

**Example output**:
```
================================================================================
REQUEST: POST http://127.0.0.1:3001/v1/chat/completions
Headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer ***'}
Request Body:
{
  "model": "gpt-5",
  "messages": [
    {
      "role": "user",
      "content": "Hello, how are you?"
    }
  ],
  "max_tokens": 100,
  "stream": false
}

RESPONSE: 200
Response Headers: {'Content-Type': 'application/json', ...}
Response Body:
{
  "id": "chatcmpl-...",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "gpt-5",
  "choices": [...],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 20,
    "total_tokens": 30
  }
}
================================================================================
```

## Example Test Run

```bash
$ make test-integration

# Or using uv directly:
$ uv run pytest tests/integration/ -m real -v

# Run specific test with request/response logging:
$ pytest tests/integration/test_chat_completions.py::TestChatCompletionsNonStreaming::test_simple_completion[gpt-5] -v --log-cli-level=INFO

tests/integration/test_models_endpoint.py::TestModelsEndpoint::test_list_models_returns_200 PASSED
tests/integration/test_models_endpoint.py::TestModelsEndpoint::test_list_models_response_format PASSED
tests/integration/test_models_endpoint.py::TestModelsEndpoint::test_list_models_contains_required_models PASSED
tests/integration/test_models_endpoint.py::TestModelsEndpoint::test_model_metadata PASSED

tests/integration/test_chat_completions.py::TestChatCompletionsNonStreaming::test_simple_completion[anthropic--claude-4.5-sonnet] PASSED
tests/integration/test_chat_completions.py::TestChatCompletionsNonStreaming::test_simple_completion[sonnet-4.5] PASSED
tests/integration/test_chat_completions.py::TestChatCompletionsNonStreaming::test_simple_completion[gpt-4.1] PASSED
tests/integration/test_chat_completions.py::TestChatCompletionsNonStreaming::test_simple_completion[gpt-5] PASSED
tests/integration/test_chat_completions.py::TestChatCompletionsNonStreaming::test_simple_completion[gemini-2.5-pro] PASSED

tests/integration/test_chat_completions.py::TestChatCompletionsStreaming::test_streaming_completion[anthropic--claude-4.5-sonnet] PASSED
tests/integration/test_chat_completions.py::TestChatCompletionsStreaming::test_streaming_completion[sonnet-4.5] PASSED
tests/integration/test_chat_completions.py::TestChatCompletionsStreaming::test_streaming_completion[gpt-4.1] PASSED
tests/integration/test_chat_completions.py::TestChatCompletionsStreaming::test_streaming_completion[gpt-5] PASSED
tests/integration/test_chat_completions.py::TestChatCompletionsStreaming::test_streaming_completion[gemini-2.5-pro] PASSED

tests/integration/test_messages_endpoint.py::TestMessagesEndpoint::test_messages_non_streaming[anthropic--claude-4.5-sonnet] PASSED
tests/integration/test_messages_endpoint.py::TestMessagesEndpoint::test_messages_non_streaming[sonnet-4.5] PASSED

======================== 50 passed in 45.23s ========================
```

## Troubleshooting

### Server Not Running

**Error**: `pytest.skip: Proxy server not running at http://127.0.0.1:3001`

**Solution**: Start the proxy server:
```bash
python proxy_server.py --config config.json
```

### Authentication Failed

**Error**: `401 Unauthorized`

**Solution**: Set valid authentication token:
```bash
export PROXY_AUTH_TOKEN="your-valid-token"
```

Or update [`test_config.json`](test_config.json):
```json
{
  "auth_token": "your-valid-token"
}
```

### Model Not Available

**Error**: `Required model 'gpt-4.1' not found in models list`

**Solution**: Ensure the model is configured in your proxy server's [`config.json`](../../config.json):
```json
{
  "subAccounts": {
    "account1": {
      "deployment_models": {
        "gpt-4.1": ["https://..."]
      }
    }
  }
}
```

### Timeout Errors

**Error**: `requests.exceptions.Timeout`

**Solution**: Increase timeout in [`test_config.json`](test_config.json):
```json
{
  "timeout": 60
}
```

### Connection Refused

**Error**: `Connection refused`

**Solution**: 
1. Check proxy server is running: `ps aux | grep proxy_server`
2. Verify correct port: `netstat -an | grep 3001`
3. Check firewall settings

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Integration Tests

on: [push, pull_request]

jobs:
  integration-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.13'
      
      - name: Install dependencies
        run: uv sync
          
      - name: Start proxy server
        run: |
          python proxy_server.py --config config.json &
          sleep 5
        env:
          PROXY_AUTH_TOKEN: ${{ secrets.PROXY_AUTH_TOKEN }}
          
      - name: Run integration tests
        run: pytest tests/integration/ -m real -v
        env:
          PROXY_AUTH_TOKEN: ${{ secrets.PROXY_AUTH_TOKEN }}
```

## Adding New Tests

### 1. Add Test to Existing File

```python
@pytest.mark.integration
@pytest.mark.real
def test_new_feature(proxy_client, proxy_url, max_tokens):
    """Test new feature."""
    response = proxy_client.post(
        f"{proxy_url}/v1/chat/completions",
        json={
            "model": "gpt-4.1",
            "messages": [{"role": "user", "content": "Test"}],
            "max_tokens": max_tokens,
        },
    )
    
    assert response.status_code == 200
    # Add assertions
```

### 2. Add New Test File

Create `tests/integration/test_new_feature.py`:

```python
"""Integration tests for new feature."""

import pytest
from validators import ResponseValidator


@pytest.mark.integration
@pytest.mark.real
class TestNewFeature:
    """Tests for new feature."""
    
    def test_something(self, proxy_client, proxy_url):
        """Test something."""
        # Your test code
        pass
```

### 3. Add New Validator

Add to [`validators.py`](test_validators.py):

```python
@staticmethod
def validate_new_format(response_data: Dict[str, Any]) -> None:
    """Validate new response format."""
    assert "new_field" in response_data
    # Add validation logic
```

## Best Practices

1. **Use descriptive test names** that explain what is being tested
2. **Use pytest markers** to categorize tests (`@pytest.mark.smoke`, etc.)
3. **Validate responses thoroughly** using [`ResponseValidator`](test_validators.py)
4. **Test both success and error cases**
5. **Use parametrize** for testing multiple models with same logic
6. **Keep tests independent** - each test should work standalone
7. **Clean up resources** if tests create any state
8. **Document complex test scenarios** with comments

## Related Documentation

- [Main Testing Documentation](../README.md)
- [Proxy Server Architecture](../../docs/ARCHITECTURE.md)
- [SAP AI Core API Documentation](../../docs/SAPAICORE_API.md)
- [Configuration Guide](../../README.md#configuration)

## Support

For issues or questions:
1. Check [Troubleshooting](#troubleshooting) section
2. Review test output for specific error messages
3. Verify proxy server logs for backend errors
4. Check configuration files are correct