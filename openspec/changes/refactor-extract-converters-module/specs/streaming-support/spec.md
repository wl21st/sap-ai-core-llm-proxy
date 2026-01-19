# Spec: Streaming Support

## ADDED Requirements

### Requirement: Streaming Chunk Conversion

The system SHALL provide conversion of streaming response chunks from AI provider formats to client-requested formats.

#### Scenario: Convert Claude chunk to OpenAI SSE
- **GIVEN** a Claude streaming chunk with `type` and `delta` fields
- **WHEN** the chunk is converted using `convert_claude_chunk_to_openai()`
- **THEN** the output SHALL be an OpenAI-formatted SSE chunk
- **AND** content SHALL be converted to `choices[0].delta.content`
- **AND** stop_reason SHALL be mapped using StopReasonMapper
- **AND** the chunk SHALL include proper `id`, `object`, `created`, and `model` fields
- **AND** finish_reason SHALL be set when appropriate

#### Scenario: Convert Claude 3.7/4 chunk to OpenAI SSE
- **GIVEN** a Claude 3.7/4 streaming chunk with extended features
- **WHEN** the chunk is converted using `convert_claude37_chunk_to_openai()`
- **THEN** the output SHALL be an OpenAI-formatted SSE chunk
- **AND** thinking/reasoning content SHALL be preserved if present
- **AND** usage metadata SHALL be extracted and logged
- **AND** all Claude 3.7-specific fields SHALL be handled correctly
- **AND** content SHALL be properly formatted for OpenAI streaming format

#### Scenario: Convert Gemini chunk to OpenAI SSE
- **GIVEN** a Gemini streaming chunk with `candidates` array
- **WHEN** the chunk is converted using `convert_gemini_chunk_to_openai()`
- **THEN** the output SHALL be an OpenAI-formatted SSE chunk
- **AND** content SHALL be extracted from candidate parts
- **AND** finishReason SHALL be mapped using StopReasonMapper
- **AND** the chunk SHALL include proper OpenAI streaming fields
- **AND** multiple candidates SHALL be handled appropriately

#### Scenario: Convert Gemini chunk to Claude delta
- **GIVEN** a Gemini streaming chunk
- **WHEN** the chunk is converted using `convert_gemini_chunk_to_claude_delta()`
- **THEN** the output SHALL be in Claude delta format
- **AND** content SHALL be extracted and formatted as Claude delta
- **AND** stop_reason SHALL be mapped using StopReasonMapper

#### Scenario: Convert OpenAI chunk to Claude delta
- **GIVEN** an OpenAI streaming chunk with `choices[0].delta`
- **WHEN** the chunk is converted using `convert_openai_chunk_to_claude_delta()`
- **THEN** the output SHALL be in Claude delta format
- **AND** content SHALL be extracted from delta.content
- **AND** the delta SHALL be formatted for Claude streaming format

### Requirement: Streaming Response Generation

The system SHALL provide streaming response generators that convert backend streaming responses to client-requested formats.

#### Scenario: Generate streaming response from Claude 3.5
- **GIVEN** a Claude 3.5 deployment URL, authentication headers, and OpenAI-format request
- **WHEN** `generate_streaming_response()` is called with model="claude-3.5-sonnet"
- **THEN** the function SHALL stream responses from the Claude API
- **AND** each chunk SHALL be converted from Claude to OpenAI SSE format
- **AND** token usage SHALL be extracted and logged at stream end
- **AND** request context (user_id, ip_address) SHALL be logged
- **AND** the generator SHALL yield properly formatted SSE chunks
- **AND** the final chunk SHALL be `data: [DONE]`

#### Scenario: Generate streaming response from Claude 3.7/4
- **GIVEN** a Claude 3.7/4 deployment URL and OpenAI-format request with thinking config
- **WHEN** `generate_streaming_response()` is called with model="claude-4.5-sonnet"
- **THEN** the function SHALL stream responses from the Claude /converse endpoint
- **AND** each chunk SHALL be converted using Claude 3.7 converter
- **AND** thinking/reasoning tokens SHALL be preserved in the stream
- **AND** cached read tokens SHALL be extracted from metadata
- **AND** token usage SHALL include cached_read_tokens if available

#### Scenario: Generate streaming response from Gemini
- **GIVEN** a Gemini deployment URL and OpenAI-format request
- **WHEN** `generate_streaming_response()` is called with model="gemini-2.5-pro"
- **THEN** the function SHALL stream responses from the Gemini API
- **AND** each chunk SHALL be converted from Gemini to OpenAI SSE format
- **AND** usageMetadata SHALL be extracted and logged
- **AND** the generator SHALL handle Gemini-specific chunk formats
- **AND** candidate selection SHALL follow Gemini behavior

#### Scenario: Generate streaming response from OpenAI
- **GIVEN** an OpenAI deployment URL and OpenAI-format request
- **WHEN** `generate_streaming_response()` is called with OpenAI model
- **THEN** the function SHALL stream responses from the OpenAI API
- **AND** chunks SHALL be passed through without conversion
- **AND** token usage SHALL be extracted and logged
- **AND** the generator SHALL handle OpenAI streaming format

#### Scenario: Handle streaming errors and timeouts
- **GIVEN** a backend API timeout or error during streaming
- **WHEN** an error occurs in `generate_streaming_response()`
- **THEN** the generator SHALL log the error
- **AND** the error SHALL be propagated to the client
- **AND** any partial response data SHALL be cleaned up
- **AND** token usage SHALL still be logged if available

#### Scenario: Generate Claude Messages API streaming response
- **GIVEN** a Claude deployment URL and Claude Messages API format request
- **WHEN** `generate_claude_streaming_response()` is called
- **THEN** the function SHALL stream responses from the backend API
- **AND** the stream SHALL be converted to Claude Messages API format
- **AND** the generator SHALL yield raw bytes for direct streaming
- **AND** the output SHALL be compatible with Claude Messages API clients

#### Scenario: Encapsulate request context for streaming
- **GIVEN** a streaming request
- **WHEN** `RequestContext` is created with user_id, ip_address, and headers
- **THEN** all context information SHALL be preserved
- **AND** the context SHALL be passed to streaming generators
- **AND** the context SHALL be used for logging and tracing
- **AND** the context SHALL not be modified during streaming

### Requirement: Streaming Token Usage Extraction

The system SHALL extract token usage from streaming response metadata for all providers.

#### Scenario: Extract token usage from Claude 3.5 streaming
- **GIVEN** a Claude 3.5 streaming response with final usage chunk
- **WHEN** the stream ends and usage metadata is available
- **THEN** input_tokens and output_tokens SHALL be extracted
- **AND** total_tokens SHALL be calculated (input + output)
- **AND** usage SHALL be logged with appropriate logger
- **AND** usage SHALL be returned to caller

#### Scenario: Extract token usage from Claude 3.7/4 streaming
- **GIVEN** a Claude 3.7/4 streaming response with usage metadata
- **WHEN** the stream ends and metadata chunk is received
- **THEN** inputTokens and outputTokens SHALL be extracted
- **AND** totalTokens SHALL be extracted
- **AND** cachedReadTokens SHALL be extracted if present
- **AND** all token counts SHALL be logged
- **AND** cached tokens SHALL be tracked separately

#### Scenario: Extract token usage from Gemini streaming
- **GIVEN** a Gemini streaming response with usageMetadata
- **WHEN** the stream ends and usageMetadata is available
- **THEN** promptTokenCount SHALL be extracted
- **AND** candidatesTokenCount SHALL be extracted
- **AND** totalTokenCount SHALL be extracted
- **AND** usage SHALL be logged with appropriate logger
- **AND** token counts SHALL be converted to OpenAI format

### Requirement: Streaming Chunk Logging

The system SHALL log streaming activity for debugging and monitoring.

#### Scenario: Log streaming request start
- **GIVEN** a streaming request is initiated
- **WHEN** `generate_streaming_response()` is called
- **THEN** the request SHALL be logged with trace ID
- **AND** model, subaccount, and deployment URL SHALL be logged
- **AND** user_id and ip_address SHALL be logged

#### Scenario: Log streaming chunks
- **GIVEN** a streaming response is being generated
- **WHEN** each chunk is processed
- **THEN** chunk activity MAY be logged at DEBUG level
- **AND** token accumulation SHALL be tracked
- **AND** performance metrics MAY be collected

#### Scenario: Log streaming completion
- **GIVEN** a streaming response is complete
- **WHEN** the stream ends
- **THEN** final token usage SHALL be logged
- **AND** streaming duration SHALL be logged
- **AND** any errors SHALL be logged
- **AND** success/failure status SHALL be logged
