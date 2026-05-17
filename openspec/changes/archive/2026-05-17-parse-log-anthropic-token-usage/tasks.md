## 1. AnthropicUsage Dataclass

- [x] 1.1 Create `utils/anthropic_usage.py` with `AnthropicUsage` dataclass: fields `input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`, `thinking_tokens` (all `int = 0`)
- [x] 1.2 Add `total_tokens` property to `AnthropicUsage` that returns the sum of all fields

## 2. AnthropicTokenUsageParser Class

- [x] 2.1 Add `AnthropicTokenUsageParser` class to `utils/anthropic_usage.py` with an `AnthropicUsage` instance as internal state
- [x] 2.2 Implement `parse_response(response: dict)` — extract `response.get("usage", {})` and populate accumulator; guard against non-dict and missing keys; catch all exceptions and log a warning
- [x] 2.3 Implement `feed_chunk(chunk: dict)` — dispatch on `chunk["type"]`: for `message_start` extract `chunk["message"]["usage"]`, for `message_delta` extract `chunk["usage"]`; silently ignore all other types; catch all exceptions and log a warning
- [x] 2.4 Implement `log(model, subaccount, user_id, ip_address)` — emit `token_usage_logger.info(...)` with the same format as existing token usage log lines; append cache/thinking counts as suffix when non-zero

## 3. Non-Streaming Integration (routers/messages.py)

- [x] 3.1 In `routers/messages.py`, after `response_json = json.loads(chunk_data)`, instantiate `AnthropicTokenUsageParser`, call `.parse_response(response_json)`, then `.log(model, subaccount_name, user_id, ip_address)` — all existing code above and below this block is unchanged
- [x] 3.2 Wrap the parser instantiation and log call in a `try/except` that only logs a warning on failure, so the `JSONResponse` is always returned regardless

## 4. Streaming Integration (handlers/streaming_generators.py)

- [x] 4.1 In `generate_bedrock_streaming_response`, instantiate `AnthropicTokenUsageParser` at the top of the function body — no changes to existing `yield` or `transport_logger` calls
- [x] 4.2 After each existing `if chunk_type == ...` branch yields its SSE event, call `parser.feed_chunk(chunk)` as an additional side-effect step
- [x] 4.3 In the `message_stop` branch, after the existing yield and `transport_logger` calls, call `parser.log(...)` to emit the usage log entry
- [x] 4.4 In the `except Exception` handler, call `parser.log(...)` with a note suffix to capture partial counts on error (existing error yield is unchanged)

## 5. Unit Tests

- [x] 5.1 Create `tests/unit/test_anthropic_usage.py` — test `AnthropicUsage`: default construction, `total_tokens` property including thinking tokens
- [x] 5.2 Test `parse_response`: full object, partial object, missing `usage` key, non-dict `usage`, exception resilience (no raise)
- [x] 5.3 Test `feed_chunk`: `message_start` populates input/cache fields, `message_delta` populates output tokens, unknown chunk types are ignored, exception resilience
- [x] 5.4 Test `log`: mock `token_usage_logger`, verify `info` called with correct field values; verify cache suffix present when non-zero; verify no call made when... (log is always called, verify format correctness)
- [x] 5.5 Verify existing tests in `tests/unit/test_streaming_generators.py` still pass unmodified

## 6. Validation

- [x] 6.1 Run `make test` — all existing tests pass
- [x] 6.2 Run `make test-cov` — new `utils/anthropic_usage.py` code paths have coverage
