# Spec: Anthropic Token Usage Logging

## Purpose
Parse and log Anthropic REST API `usage` fields (core tokens, cache tokens, thinking tokens) with resiliency for both streaming and non-streaming responses via the existing `token_usage_logger` infrastructure.

## ADDED Requirements

### Requirement: AnthropicUsage dataclass holds all known usage fields
The system SHALL provide an `AnthropicUsage` dataclass with integer fields `input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`, and `thinking_tokens`, all defaulting to `0`. It SHALL expose a `total_tokens` property that sums all fields.

#### Scenario: Default construction yields zero counts
- **WHEN** `AnthropicUsage()` is constructed with no arguments
- **THEN** all token fields are `0` and `total_tokens` returns `0`

#### Scenario: total_tokens includes thinking tokens
- **WHEN** `AnthropicUsage(input_tokens=10, output_tokens=5, thinking_tokens=3)` is constructed
- **THEN** `total_tokens` returns `18`

### Requirement: AnthropicTokenUsageParser parses non-streaming responses
The `AnthropicTokenUsageParser` class SHALL provide a `parse_response(response: dict)` method that extracts the `usage` object from an Anthropic REST response dict and populates its internal `AnthropicUsage` accumulator. Missing or malformed fields SHALL default to `0`. Any exception SHALL be caught internally and logged as a warning without propagating.

#### Scenario: Full usage object parsed
- **WHEN** `parse_response` is called with a response containing a complete `usage` dict
- **THEN** all fields of the internal `AnthropicUsage` are correctly populated

#### Scenario: Partial usage object defaults missing fields
- **WHEN** `parse_response` is called with a response whose `usage` has only `input_tokens` and `output_tokens`
- **THEN** cache and thinking fields remain `0`

#### Scenario: Missing usage key is resilient
- **WHEN** `parse_response` is called with a response dict that has no `usage` key
- **THEN** the accumulator remains all-zero and a warning is logged; no exception is raised

#### Scenario: Non-dict usage value is resilient
- **WHEN** `parse_response` is called and `usage` is not a dict (e.g., `None` or an integer)
- **THEN** the accumulator remains all-zero and a warning is logged; no exception is raised

### Requirement: AnthropicTokenUsageParser accumulates usage across SSE streaming events
The `AnthropicTokenUsageParser` class SHALL provide a `feed_chunk(chunk: dict)` method. Calling it with an Anthropic SSE chunk SHALL update the internal accumulator: `message_start` chunks populate input tokens and cache fields; `message_delta` chunks populate output tokens. All other chunk types SHALL be silently ignored. Any exception SHALL be caught internally and logged as a warning.

#### Scenario: message_start populates input tokens
- **WHEN** `feed_chunk` is called with a `message_start` chunk containing `message.usage.input_tokens`
- **THEN** the accumulator's `input_tokens` is updated

#### Scenario: message_start populates cache fields
- **WHEN** `feed_chunk` is called with a `message_start` chunk containing cache token fields
- **THEN** `cache_creation_input_tokens` and `cache_read_input_tokens` are updated accordingly

#### Scenario: message_delta populates output tokens
- **WHEN** `feed_chunk` is called with a `message_delta` chunk containing `usage.output_tokens`
- **THEN** the accumulator's `output_tokens` is updated

#### Scenario: Unknown chunk types are silently ignored
- **WHEN** `feed_chunk` is called with a `content_block_delta` or any unrecognized chunk type
- **THEN** the accumulator is unchanged and no warning is logged

### Requirement: AnthropicTokenUsageParser logs token usage via token_usage_logger
The `AnthropicTokenUsageParser` class SHALL provide a `log(model, subaccount, user_id, ip_address)` method that emits a `token_usage_logger.info` entry using the same format as existing token usage log lines. Cache and thinking token counts SHALL be appended to the log message when non-zero.

#### Scenario: Basic log entry emitted
- **WHEN** `log(model="claude-4.5", subaccount="acct1", user_id="u1", ip_address="1.2.3.4")` is called after parsing
- **THEN** `token_usage_logger.info` is called with model, subaccount, input_tokens, output_tokens, and total_tokens

#### Scenario: Cache suffix appended when non-zero
- **WHEN** the accumulator has non-zero `cache_creation_input_tokens` or `cache_read_input_tokens`
- **THEN** the log message includes cache token counts

#### Scenario: Existing token processing and logging code is unchanged
- **WHEN** the Anthropic token usage parser is added to the codebase
- **THEN** all existing token logging calls in `handlers/streaming_generators.py` and `routers/chat.py` are not modified
