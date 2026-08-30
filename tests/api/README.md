# Direct Bedrock API Tests

This directory contains tests that interact directly with SAP AI Core's AWS Bedrock endpoint using the SAP AI SDK (`gen_ai_hub.proxy.native.amazon.clients.ClientWrapper`).

---

## 1. Purpose

- **Direct API Tests (`tests/api/`)**: Validate upstream AWS Bedrock acceptance and rejection behavior directly, verifying which Anthropic parameters Bedrock accepts (HTTP 200) vs rejects (HTTP 400).
- **Integration Tests (`tests/integration/`)**: Verify that the proxy server automatically strips unsupported fields and returns clean responses to clients.

---

## 2. Prerequisites & Setup

1. Configure SAP AI Core credentials at `~/.aicore/config.json`:
   ```bash
   mkdir -p ~/.aicore
   cp /path/to/account_key.json ~/.aicore/config.json
   chmod 600 ~/.aicore/config.json
   ```

2. Ensure target models are configured in `deployment_models` (e.g. `sonnet-4.6`, `opus-4.7`, `haiku-4.5`).

---

## 3. Running API Tests

```bash
# Run all direct Bedrock API tests
uv run pytest tests/api/ -v

# Run for a specific model
uv run pytest tests/api/ -k "sonnet-4.6" -v

# Run with verbose logs
uv run pytest tests/api/ -v --log-cli-level=INFO
```

---

## 4. Test Matrix & Unsupported Fields Findings

| Test Case | Payload Tested | Bedrock Direct Behavior | Proxy Stripping Action |
|---|---|---|---|
| `test_metadata_field_rejected` | `metadata: {user_id: ...}` | HTTP 200 (ignored) or 400 | Stripped by proxy |
| `test_output_config_field_rejected` | `output_config: {...}` | **HTTP 400 (Rejected)** | **Stripped by proxy** |
| `test_context_management_field_rejected` | `context_management: {...}` | **HTTP 400 (Rejected)** | **Stripped by proxy** |
| `test_all_unsupported_fields_rejected` | All combined | **HTTP 400 (Rejected)** | **Stripped by proxy** |
| `test_valid_request_succeeds` | Clean request | HTTP 200 OK | Preserved |
| `test_thinking_without_context_management` | `thinking: {type: "enabled"}` | HTTP 200 OK | Preserved |
| `test_cache_control_supported` | `cache_control: {type: "ephemeral"}` | HTTP 200 OK | Preserved |
