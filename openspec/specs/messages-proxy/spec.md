# Messages Proxy

## Purpose
Define the `/v1/messages` endpoint proxy behavior, including token usage logging for both streaming and non-streaming paths using the raw Anthropic usage object.

## Requirements

### Requirement: Token usage logging for non-streaming responses

The system SHALL log token usage after receiving a complete response from the Anthropic `/v1/messages` endpoint.

#### Scenario: Non-streaming token usage log
- **WHEN** a non-streaming POST request is sent to `/v1/messages`
- **AND** the backend returns a response containing a `usage` field
- **THEN** the system SHALL emit a `token_usage_logger.info` entry with format:
  `User: %s, IP: %s, Model: %s, SubAccount: %s, Usage: %s (Non-Streaming)`
- **AND** the `Usage` value SHALL be `json.dumps(usage)` — the raw object as returned by Anthropic
- **AND** no change is made to the response content returned to the client

### Requirement: Token usage logging for streaming responses

The system SHALL log aggregated token usage after a streaming `/v1/messages` response completes.

#### Scenario: Streaming token usage accumulation and log
- **WHEN** a streaming POST request is sent to `/v1/messages`
- **AND** the backend streams SSE chunks
- **THEN** the system SHALL accumulate usage by merging chunk data:
  - `message_start` chunk → `usage.update(message.usage)`
  - `message_delta` chunk → `usage.update(chunk.usage)` (overwrites `output_tokens` with final value)
- **AND** after yielding the `message_stop` event, before `data: [DONE]`, the system SHALL emit a `token_usage_logger.info` entry with format:
  `User: %s, IP: %s, Model: %s, SubAccount: %s, Usage: %s (Streaming)`
- **AND** the `Usage` value SHALL be `json.dumps(merged_usage_dict)` — the raw merged object
- **AND** all chunks SHALL be yielded unchanged (pass-through behavior preserved)
- **AND** when `request is None`, no log entry SHALL be emitted

### Requirement: Raw usage object preserved without field filtering

The system SHALL log the Anthropic usage object as-is so that all present and future fields are captured without requiring proxy code changes.

#### Scenario: Future usage fields captured automatically
- **WHEN** Anthropic adds new usage fields (e.g., `cache_creation.ephemeral_5m_input_tokens`, `thinking_tokens`, `web_search_requests`)
- **THEN** those fields SHALL appear in the logged usage JSON without any proxy code changes
- **AND** no usage fields SHALL be renamed or filtered

### Requirement: User ID truncation in log entries

The system SHALL truncate user identifiers longer than 20 characters in log entries.

#### Scenario: Long user ID truncated
- **WHEN** the authenticated user ID exceeds 20 characters
- **THEN** the logged user value SHALL be truncated to 20 characters followed by `...`
- **AND** the full user ID SHALL NOT appear in the log entry
