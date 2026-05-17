## Why

The `/v1/messages` endpoint proxies Anthropic Claude REST API responses but never extracts or logs token usage data (input tokens, output tokens, cache metrics, thinking tokens). This creates a blind spot in usage monitoring — the `token_usage` logger that already works for `/v1/chat/completions` emits nothing for the Anthropic Messages API path, leaving billing and capacity planning without visibility into a primary traffic source.

## What Changes

- Add a utility function to safely parse Anthropic REST response `usage` objects, covering all known fields: `input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`, `thinking_tokens` (where present)
- Log parsed token usage via the existing `token_usage_logger` in both the non-streaming and streaming paths of the Anthropic Messages API (`routers/messages.py`, `handlers/streaming_generators.py`)
- All parsing is resilient: missing fields default to 0/None and any parse error is caught and logged as a warning without disrupting the response stream
- Add unit tests covering the parser and log output for non-streaming and streaming cases

## Capabilities

### New Capabilities

- `anthropic-token-usage-logging`: Parse and log Anthropic REST API `usage` fields (core tokens, cache tokens, thinking tokens) with resiliency for both streaming and non-streaming responses

### Modified Capabilities

<!-- No existing spec-level behavior changes -->

## Impact

- `routers/messages.py` — non-streaming path: parse `response_json["usage"]` and emit `token_usage_logger.info(...)` before returning `JSONResponse`
- `handlers/streaming_generators.py` — `generate_bedrock_streaming_response`: extract usage from `message_start` chunk (initial input tokens) and `message_delta` chunk (output tokens, stop reason), then log at stream end
- New helper: `utils/anthropic_usage.py` (or inline in `handlers/streaming_generators.py`) — `parse_anthropic_usage(usage_dict)` returns a typed dict / dataclass of all known usage fields
- No API contract changes, no breaking changes
- Existing `token_usage_logger` infrastructure reused; no new log destinations
