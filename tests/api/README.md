# Direct Bedrock API Tests

This directory contains tests that hit SAP AI Core Bedrock **directly** using the SDK, NOT via the proxy server. These are different from integration tests.

## Purpose

- **Integration tests** (`tests/integration/`) - Test the proxy server endpoints
- **API tests** (`tests/api/`) - Test Bedrock backend directly via SDK

## Prerequisites

1. **SAP AI Core Credentials**: Configure `~/.aicore/config.json` with your account_key.json
   ```bash
   # The SDK will automatically load this
   ls ~/.aicore/config.json
   ```

2. **Configured Models**: Your config must have deployment URLs for tested models

## Running Tests

```bash
# Run all direct API tests
pytest tests/api/ -v

# Run specific test file
pytest tests/api/test_bedrock_unsupported_fields.py -v

# Run tests with specific marker
pytest tests/api/ -m bedrock -v

# Run with logging
pytest tests/api/ -v --log-cli-level=INFO
```

## Test Structure

### `conftest.py`
Pytest fixtures for Bedrock integration:
- `proxy_config` - Loads SAP AI Core config from `~/.aicore/config.json`
- `first_subaccount` - Gets first configured subaccount
- `bedrock_client_factory` - Factory to create Bedrock clients for any model

### `test_bedrock_unsupported_fields.py`

**Purpose**: Verify which Anthropic fields Bedrock supports/rejects

**Test Models** (as requested):
- `sonnet-4.6` - Sonnet model family
- `opus-4.7` - Opus model family  
- `haiku-4.5` - Haiku model family

**Test Cases** (per model):

1. **test_metadata_field_rejected** (NEGATIVE)
   - Sends `metadata` field to Bedrock
   - Expected: HTTP 400 Bad Request
   - Proves: Proxy must strip this field

2. **test_output_config_field_rejected** (NEGATIVE)
   - Sends `output_config` field to Bedrock
   - Expected: HTTP 400 Bad Request
   - Proves: Proxy must strip this field

3. **test_context_management_field_rejected** (NEGATIVE)
   - Sends `context_management` field to Bedrock
   - Expected: HTTP 400 Bad Request
   - Proves: Proxy must strip this field

4. **test_all_unsupported_fields_rejected** (NEGATIVE)
   - Sends all three unsupported fields together
   - Expected: HTTP 400 Bad Request
   - Proves: Proxy must strip ALL of them

5. **test_valid_request_succeeds** (POSITIVE - Control)
   - Sends clean request without unsupported fields
   - Expected: HTTP 200 with valid response
   - Proves: Bedrock client and config work

6. **test_thinking_without_context_management_accepted** (POSITIVE)
   - Sends valid thinking config (no nested context_management)
   - Expected: HTTP 200
   - Proves: Proxy only strips context_management, not thinking itself

## Example Output

```
tests/api/test_bedrock_unsupported_fields.py::TestBedrockUnsupportedFieldsDirectAPI::test_metadata_field_rejected[sonnet-4.6] PASSED
✓ Confirmed: Bedrock rejects metadata for sonnet-4.6 (HTTP 400)

tests/api/test_bedrock_unsupported_fields.py::TestBedrockUnsupportedFieldsDirectAPI::test_valid_request_succeeds[opus-4.7] PASSED
✓ Confirmed: Valid requests work for opus-4.7 (HTTP 200)
```

## Troubleshooting

### "Could not load SAP AI Core config"
```bash
# Check config exists
cat ~/.aicore/config.json

# Or set via environment
export SAP_AI_CORE_CONFIG_PATH=/path/to/account_key.json
```

### "Model X not configured in subaccount"
```bash
# Check available models in config
cat ~/.aicore/config.json | jq '.subAccounts[].deployment_models'

# Or skip that model in tests:
pytest tests/api/ -k "not haiku-4.5"
```

### Connection Errors
```bash
# Check SAP AI Core connectivity
# Ensure account_key.json credentials are valid
# Check TLS certificates if needed
```

## Integration with CI/CD

```yaml
# Example GitHub Actions
- name: Run Direct Bedrock API Tests
  env:
    SAP_AI_CORE_CONFIG_PATH: ${{ secrets.SAP_AI_CORE_CONFIG }}
  run: pytest tests/api/ -v --tb=short
```

## Comparing with Integration Tests

| Aspect | Integration Tests | API Tests |
|--------|-------------------|-----------|
| **Target** | Proxy server | Bedrock backend |
| **Location** | `/v1/messages` endpoint | Direct SDK invocation |
| **Config** | Uses proxy auth token | Uses account_key.json |
| **Speed** | Faster (proxy layer) | Slower (backend calls) |
| **Purpose** | Test proxy behavior | Test backend support |
| **Scope** | Unit of proxy | Unit of Bedrock |
| **Models** | Any proxy-configured | Direct Bedrock models |

## Adding New Tests

When adding new direct Bedrock API tests:

1. Use the `bedrock_client_factory` fixture to get clients
2. Mark with `@pytest.mark.api` and `@pytest.mark.bedrock`
3. Parametrize over TEST_MODELS list
4. Document expected vs actual behavior
5. Clearly indicate NEGATIVE vs POSITIVE tests

Example:
```python
@pytest.mark.parametrize("model", TEST_MODELS)
def test_my_new_field(self, model: str, bedrock_client_factory):
    """
    NEGATIVE TEST: Verify Bedrock rejects my_new_field.
    """
    try:
        client = bedrock_client_factory(model)
    except Exception as e:
        pytest.skip(f"Could not get Bedrock client for {model}: {e}")
    
    # Test implementation
    assert status == 400, "Expected rejection"
```

## References

- [SAP AI Core Documentation](https://help.sap.com/docs/sap-ai-core)
- [AWS Bedrock Claude API](https://docs.aws.amazon.com/bedrock/latest/userguide/)
- [Anthropic Messages API](https://docs.anthropic.com/en/api/messages)
