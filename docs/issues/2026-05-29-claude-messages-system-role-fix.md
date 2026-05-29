# Claude /v1/messages system-role fix

## Summary

This note documents the fix for a Bedrock `ValidationException` triggered by Claude `/v1/messages` requests when a `system` role message was forwarded inside the `messages` array.

Observed upstream error:

```text
messages: Unexpected role "system". The Messages API accepts a top-level `system` parameter, not "system" as an input message role.
```

The fix was implemented in `routers/messages.py` inside `proxy_claude_request()`.

## Root cause

Before the fix, the route only extracted a `system` message when it was the first item in the incoming `messages` array.

That meant requests like this were still possible to forward to Bedrock:

```json
{
  "model": "anthropic--claude-4.5-sonnet",
  "messages": [
    {"role": "user", "content": "Hello"},
    {"role": "system", "content": "Be concise"}
  ],
  "stream": true
}
```

Bedrock's Claude Messages API rejects any `system` role inside `messages`. It only accepts the system prompt via the top-level `system` field.

## Fix implemented

`proxy_claude_request()` now:

1. scans the full incoming `messages` array
2. removes every `system` role message regardless of position
3. extracts text from each removed `system` message
4. concatenates multiple non-empty system prompts with `\n\n`
5. writes the result to top-level `body["system"]`
6. forwards a cleaned `body["messages"]` array with no `system` roles

This applies to both streaming and non-streaming `/v1/messages` requests because both paths share the same payload preparation logic before the Bedrock invocation.

## Files changed

- `routers/messages.py`
- `tests/unit/test_messages_blueprint.py`

## Payload transformation stages

The request passes through the following stages inside `proxy_claude_request()`.

### Stage 1: inbound Anthropic-compatible request

The FastAPI route receives a Claude-compatible payload from the client.

Example incoming request:

```json
{
  "model": "anthropic--claude-4.5-sonnet",
  "messages": [
    {"role": "user", "content": "Hello"},
    {"role": "system", "content": "Be concise"}
  ],
  "stream": true,
  "max_tokens": 128
}
```

Relevant code:

- `routers/messages.py` reads `request_body_json`
- `conversation = request_body_json.get("messages", [])`

### Stage 2: message normalization and system extraction

The route iterates through `conversation` and splits it into:

- `messages_list`: all non-system messages
- `system_message`: extracted system prompt text

Current behavior:

- any `{"role": "system", ...}` message is removed from `messages_list`
- string content is used directly
- list content is flattened via `Converters._extract_text_from_content()`
- multiple system prompts are joined with blank lines
- empty system prompts are still removed from `messages`

Example after extraction:

```json
{
  "messages_list": [
    {"role": "user", "content": "Hello"}
  ],
  "system_message": "Be concise"
}
```

Relevant code:

- `routers/messages.py` around the `system_message` and `messages_list` preparation block
- helper used for nested content extraction: `proxy_helpers.py`, `Converters._extract_text_from_content()`

### Stage 3: request body cloning and Bedrock shaping

The route then clones the request body and rewrites it for Bedrock:

- removes `model`
- removes `stream`
- sets `anthropic_version`
- overwrites `messages` with cleaned `messages_list`
- adds top-level `system` if extracted

Example transformed body before additional cleanup:

```json
{
  "messages": [
    {"role": "user", "content": "Hello"}
  ],
  "system": "Be concise",
  "max_tokens": 128,
  "anthropic_version": "bedrock-2023-05-31"
}
```

Relevant code:

- `body = deepcopy(request_body_json)`
- `body.pop("model", None)`
- `body.pop("stream", None)`
- `body["anthropic_version"] = API_VERSION_BEDROCK_2023_05_31`
- `body["messages"] = messages_list`
- `body["system"] = system_message`

### Stage 4: payload cleanup for Bedrock compatibility

After system extraction, the route applies further cleanup before serialization:

- removes unsupported top-level fields:
  - `context_management`
  - `metadata`
  - `output_config`
- removes `thinking.context_management` if present
- removes `input_examples` from tools and nested custom tool definitions
- removes empty text blocks from message content arrays
- adjusts `max_tokens` when `thinking.budget_tokens` requires a higher value

This stage is independent of the system-role fix, but it is part of the final payload preparation before the Bedrock request.

### Stage 5: debug summary before send

A debug log was added to confirm the final outbound shape:

```text
Final Bedrock Claude payload summary: message_roles=['user'], has_system=True
```

This log confirms two critical invariants:

1. no `system` role remains in `body["messages"]`
2. a top-level `system` field exists when expected

Relevant code:

- `logger.debug("Final Bedrock Claude payload summary: ...")`

### Stage 6: serialized payload sent to Bedrock

The route serializes the cleaned body using:

```python
body_json = json.dumps(body)
```

Then it sends the payload through one of these paths:

- streaming: `invoke_bedrock_streaming(bedrock_client, body_json)`
- non-streaming: `invoke_bedrock_non_streaming(bedrock_client, body_json)`

Because the fix happens before this branch, both request modes receive the corrected payload shape.

## Before vs after

### Before fix

Possible outgoing payload:

```json
{
  "messages": [
    {"role": "user", "content": "Hello"},
    {"role": "system", "content": "Be concise"}
  ],
  "anthropic_version": "bedrock-2023-05-31",
  "max_tokens": 128
}
```

Result:

- Bedrock returned HTTP 400
- error: `Unexpected role "system"`

### After fix

Outgoing payload:

```json
{
  "messages": [
    {"role": "user", "content": "Hello"}
  ],
  "system": "Be concise",
  "anthropic_version": "bedrock-2023-05-31",
  "max_tokens": 128
}
```

Result:

- payload shape matches Bedrock Claude Messages API requirements

## Verification performed

Automated tests run:

```bash
uv run pytest tests/unit/test_messages_blueprint.py
```

Result at time of fix:

- `9 passed`

Important regression coverage added:

- system message is removed even when not first in the `messages` array
- streaming path receives the cleaned payload
- top-level `system` field is populated correctly

## Handoff notes

- The fix is localized to the `/v1/messages` Claude route in `routers/messages.py`.
- The change does not modify OpenAI chat routing or the generic converter entry points.
- If future clients send multiple `system` messages, the current behavior is to concatenate them with blank lines.
- If future work centralizes Anthropic-to-Bedrock conversion, this route-level extraction logic should either move into that shared converter or remain the canonical normalization step.

## Recommended runtime check

When validating in logs, look for:

```text
Final Bedrock Claude payload summary: message_roles=[...], has_system=...
```

Healthy signal for the original failure case:

```text
Final Bedrock Claude payload summary: message_roles=['user'], has_system=True
```

Unhealthy signal:

```text
Final Bedrock Claude payload summary: message_roles=['user', 'system'], has_system=False
```

The unhealthy case would indicate regression in payload normalization before the Bedrock call.
