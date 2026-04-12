## 1. Fix Default Values

- [x] 1.1 In `routers/messages.py:155`, change `request_body_json.get("stream", True)` to `request_body_json.get("stream", False)`
- [x] 1.2 In `handlers/model_handlers.py:38`, change `payload.get("stream", True)` to `payload.get("stream", False)`
- [x] 1.3 In `handlers/model_handlers.py:92`, change `payload.get("stream", True)` to `payload.get("stream", False)` (Gemini handler has the same default bug)

## 2. Test Coverage — messages endpoint

- [x] 2.1 In `tests/unit/test_messages_blueprint.py`, add test: POST `/v1/messages` with no `stream` field → asserts `invoke_bedrock_non_streaming` is called (not streaming)
- [x] 2.2 Add test: POST `/v1/messages` with `"stream": false` → asserts `invoke_bedrock_non_streaming` is called
- [x] 2.3 Verify existing test with `"stream": true` still passes (regression check)

## 3. Test Coverage — Claude model handler

- [x] 3.1 In `tests/unit/` (or create `tests/unit/handlers/test_model_handlers.py`), add test: `handle_claude_request()` with no `stream` in payload → asserts endpoint path is `/converse` (Claude 3.7/4) or `/invoke` (older)
- [x] 3.2 Add test: `handle_claude_request()` with `"stream": false` → same non-streaming endpoint assertion

## 4. Test Coverage — chat router

- [x] 4.1 In `tests/unit/routers/test_chat_router.py`, add test: POST `/v1/chat/completions` with no `stream` field → asserts `_handle_non_streaming_request` is called (already defaults to False, regression guard)

## 5. Verify

- [x] 5.1 Run `make test` and confirm all tests pass with no regressions
