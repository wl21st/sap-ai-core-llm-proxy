# Spec: Format Converters

## ADDED Requirements

### Requirement: Request Format Conversion

The system SHALL provide request payload conversion between different AI provider formats.

#### Scenario: Convert OpenAI request to Claude 3.5 format
- **GIVEN** an OpenAI-format chat completion request with model "claude-3.5-sonnet"
- **WHEN** the request is converted using `convert_openai_to_claude()`
- **THEN** the output SHALL be in Claude Messages API format
- **AND** messages SHALL be converted from OpenAI format to Claude format
- **AND** system messages SHALL be placed in the `system` field
- **AND** user/assistant messages SHALL be converted to `content` blocks
- **AND** parameters like `max_tokens`, `temperature` SHALL be mapped correctly

#### Scenario: Convert OpenAI request to Claude 3.7/4 format
- **GIVEN** an OpenAI-format chat completion request with model "claude-4.5-sonnet"
- **WHEN** the request is converted using `convert_openai_to_claude37()`
- **THEN** the output SHALL be in Claude /converse API format
- **AND** the request SHALL include `anthropic_version` header value
- **AND** messages SHALL be converted with proper Claude 3.7 structure
- **AND** `thinking` configuration SHALL be preserved if present

#### Scenario: Convert OpenAI request to Gemini format
- **GIVEN** an OpenAI-format chat completion request with model "gemini-2.5-pro"
- **WHEN** the request is converted using `convert_openai_to_gemini()`
- **THEN** the output SHALL be in Gemini API format
- **AND** messages SHALL be converted to `contents` array
- **AND** system instructions SHALL be placed in `system_instruction` field
- **AND** parameters SHALL be mapped to Gemini schema

#### Scenario: Convert Claude request to OpenAI format
- **GIVEN** a Claude-format Messages API request
- **WHEN** the request is converted using `convert_claude_request_to_openai()`
- **THEN** the output SHALL be in OpenAI chat completion format
- **AND** messages SHALL be converted from Claude to OpenAI format
- **AND** system messages SHALL be converted to OpenAI system messages
- **AND** tool definitions SHALL be converted to OpenAI tools format

#### Scenario: Convert Claude request to Gemini format
- **GIVEN** a Claude-format Messages API request
- **WHEN** the request is converted using `convert_claude_request_to_gemini()`
- **THEN** the output SHALL be in Gemini API format
- **AND** messages SHALL be converted to Gemini contents array
- **AND** Claude-specific fields SHALL be mapped to Gemini equivalents

#### Scenario: Convert Claude request to Bedrock format
- **GIVEN** a Claude-format Messages API request
- **WHEN** the request is converted using `convert_claude_request_for_bedrock()`
- **THEN** the output SHALL be in AWS Bedrock format
- **AND** model ID SHALL be extracted and placed in `modelId` field
- **AND** request body SHALL be formatted for Bedrock Invoke API
- **AND** authentication headers SHALL be excluded from the converted payload

### Requirement: Response Format Conversion

The system SHALL provide response payload conversion from AI provider formats to client-requested formats.

#### Scenario: Convert Claude response to OpenAI format
- **GIVEN** a Claude API response with `content`, `stop_reason`, and `usage`
- **WHEN** the response is converted using `convert_claude_to_openai()`
- **THEN** the output SHALL be in OpenAI chat completion format
- **AND** content SHALL be converted to `choices[0].message.content`
- **AND** stop_reason SHALL be mapped using StopReasonMapper
- **AND** usage SHALL be converted to OpenAI format (prompt_tokens, completion_tokens, total_tokens)
- **AND** finish_reason SHALL be set to "stop" by default

#### Scenario: Convert Claude 3.7/4 response to OpenAI format
- **GIVEN** a Claude 3.7/4 API response with extended features
- **WHEN** the response is converted using `convert_claude37_to_openai()`
- **THEN** the output SHALL be in OpenAI chat completion format
- **AND** thinking/reasoning content SHALL be preserved if present
- **AND** usage SHALL include cached_read_tokens if available
- **AND** all Claude 3.7-specific fields SHALL be handled correctly

#### Scenario: Convert Gemini response to OpenAI format
- **GIVEN** a Gemini API response with `candidates`, `usageMetadata`
- **WHEN** the response is converted using `convert_gemini_to_openai()`
- **THEN** the output SHALL be in OpenAI chat completion format
- **AND** candidates SHALL be converted to `choices` array
- **AND** usageMetadata SHALL be converted to OpenAI usage format
- **AND** finishReason SHALL be mapped using StopReasonMapper
- **AND** content SHALL be extracted from candidate parts

#### Scenario: Convert Gemini response to Claude format
- **GIVEN** a Gemini API response
- **WHEN** the response is converted using `convert_gemini_response_to_claude()`
- **THEN** the output SHALL be in Claude Messages API format
- **AND** content SHALL be converted to Claude content blocks
- **AND** usage SHALL be converted to Claude format (input_tokens, output_tokens)
- **AND** stop_reason SHALL be mapped using StopReasonMapper

#### Scenario: Convert OpenAI response to Claude format
- **GIVEN** an OpenAI API response
- **WHEN** the response is converted using `convert_openai_response_to_claude()`
- **THEN** the output SHALL be in Claude Messages API format
- **AND** message content SHALL be converted to Claude format
- **AND** usage SHALL be converted to Claude format
- **AND** finish_reason SHALL be mapped using StopReasonMapper

### Requirement: Stop Reason Mapping

The system SHALL provide bidirectional mapping of stop/finish reasons between AI providers.

#### Scenario: Map Claude stop reason to OpenAI
- **GIVEN** a Claude stop reason "end_turn"
- **WHEN** `StopReasonMapper.claude_to_openai()` is called
- **THEN** the mapped reason SHALL be "stop"
- **AND** given "max_tokens", the mapped reason SHALL be "length"
- **AND** given "stop_sequence", the mapped reason SHALL be "stop"
- **AND** given "tool_use", the mapped reason SHALL be "tool_calls"

#### Scenario: Map OpenAI stop reason to Claude
- **GIVEN** an OpenAI stop reason "stop"
- **WHEN** `StopReasonMapper.openai_to_claude()` is called
- **THEN** the mapped reason SHALL be "end_turn"
- **AND** given "length", the mapped reason SHALL be "max_tokens"
- **AND** given "content_filter", the mapped reason SHALL be "stop_sequence"
- **AND** given "tool_calls", the mapped reason SHALL be "tool_use"

#### Scenario: Map Gemini stop reason to OpenAI
- **GIVEN** a Gemini finishReason "STOP"
- **WHEN** `StopReasonMapper.gemini_to_openai()` is called
- **THEN** the mapped reason SHALL be "stop"
- **AND** given "MAX_TOKENS", the mapped reason SHALL be "length"
- **AND** given "SAFETY" or "RECITATION", the mapped reason SHALL be "content_filter"
- **AND** given any other value, the mapped reason SHALL be "stop" (default)

### Requirement: API Version Constants

The system SHALL provide API version constants for different providers.

#### Scenario: Use API version constants in converters
- **GIVEN** the `converters` module is imported
- **WHEN** `API_VERSION_2023_05_15` is accessed
- **THEN** the value SHALL be "2023-05-15"
- **AND** when `API_VERSION_2024_12_01_PREVIEW` is accessed
- **AND** the value SHALL be "2024-12-01-preview"
- **AND** these constants SHALL be used in converter functions
