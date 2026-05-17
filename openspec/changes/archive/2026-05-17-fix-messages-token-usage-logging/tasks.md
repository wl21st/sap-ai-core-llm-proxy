# Tasks: fix-messages-token-usage-logging

## Implementation Tasks

- [x] Extend `generate_bedrock_streaming_response` signature with `request`, `model`, `subaccount_name` parameters
- [x] Accumulate `input_tokens` and cache fields from `message_start` chunk
- [x] Accumulate `output_tokens` from `message_delta` chunk
- [x] Emit `token_usage_logger.info(...)` after `message_stop` in streaming generator
- [x] Update `generate_bedrock_streaming_response_sync` to pass through new parameters
- [x] Update call site in `routers/messages.py` to pass `request`, `model`, `subaccount_name`
- [x] Add `token_usage_logger` import to `routers/messages.py`
- [x] Add non-streaming token usage logging after `response_json = json.loads(chunk_data)`
- [x] Add unit tests for streaming path token logging
- [x] Add unit tests for non-streaming path token logging
- [x] Add unit tests for cache field conditional inclusion
