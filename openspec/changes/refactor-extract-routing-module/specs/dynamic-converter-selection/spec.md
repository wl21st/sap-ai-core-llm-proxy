# Spec: Dynamic Converter Selection

## ADDED Requirements

### Requirement: Protocol-Based Converter Selection

The system SHALL select format converters dynamically based on model detection and API protocol.

#### Scenario: Select Claude 3.5 converter
- **GIVEN** a model "claude-3.5-sonnet" detected by `Detector`
- **WHEN** protocol is determined as "ClaudeInvoke"
- **THEN** request converter SHALL be `convert_openai_to_claude`
- **AND** response converter SHALL be `convert_claude_to_openai`
- **AND** streaming chunk converter SHALL be `convert_claude_chunk_to_openai`

#### Scenario: Select Claude 3.7/4 converter
- **GIVEN** a model "claude-4.5-sonnet" detected by `Detector`
- **WHEN** protocol is determined as "ClaudeConverse"
- **THEN** request converter SHALL be `convert_openai_to_claude37`
- **AND** response converter SHALL be `convert_claude37_to_openai`
- **AND** streaming chunk converter SHALL be `convert_claude37_chunk_to_openai`

#### Scenario: Select Gemini converter
- **GIVEN** a model "gemini-2.5-pro" detected by `Detector`
- **WHEN** protocol is determined as "GeminiGenerate"
- **THEN** request converter SHALL be `convert_openai_to_gemini`
- **AND** response converter SHALL be `convert_gemini_to_openai`
- **AND** streaming chunk converter SHALL be `convert_gemini_chunk_to_openai`

#### Scenario: Select OpenAI converter (pass-through)
- **GIVEN** a model "gpt-4o" detected by `Detector`
- **WHEN** protocol is determined as "OpenAIChat"
- **THEN** request converter SHALL pass through payload with minimal normalization
- **AND** response converter SHALL pass through with minimal transformation
- **AND** no format conversion SHALL occur

### Requirement: Protocol Handler Abstraction

The system SHALL encapsulate protocol-specific logic in dedicated handler classes.

#### Scenario: ClaudeConverseProtocol handler
- **GIVEN** the ClaudeConverseProtocol class
- **WHEN** `build_endpoint()` is called
- **THEN** endpoint SHALL be `/converse` or `/converse-stream` based on stream flag
- **WHEN** `get_request_converter()` is called
- **THEN** `convert_openai_to_claude37` SHALL be returned
- **WHEN** `get_response_converter()` is called
- **THEN** `convert_claude37_to_openai` SHALL be returned

#### Scenario: ClaudeInvokeProtocol handler
- **GIVEN** the ClaudeInvokeProtocol class
- **WHEN** `build_endpoint()` is called
- **THEN** endpoint SHALL be `/invoke` or `/invoke-with-response-stream` based on stream flag
- **WHEN** `get_request_converter()` is called
- **THEN** `convert_openai_to_claude` SHALL be returned
- **WHEN** `get_response_converter()` is called
- **THEN** `convert_claude_to_openai` SHALL be returned

#### Scenario: GeminiGenerateProtocol handler
- **GIVEN** the GeminiGenerateProtocol class
- **WHEN** `build_endpoint()` is called
- **THEN** endpoint SHALL be `/models/{model}:generateContent` or `/models/{model}:streamGenerateContent`
- **WHEN** `get_request_converter()` is called
- **THEN** `convert_openai_to_gemini` SHALL be returned
- **WHEN** `get_response_converter()` is called
- **THEN** `convert_gemini_to_openai` SHALL be returned

#### Scenario: OpenAIChatProtocol handler
- **GIVEN** the OpenAIChatProtocol class
- **WHEN** `build_endpoint()` is called
- **THEN** endpoint SHALL be `/chat/completions` with appropriate API version
- **WHEN** `get_request_converter()` is called
- **THEN** pass-through function SHALL be returned
- **WHEN** `get_response_converter()` is called
- **THEN** pass-through function SHALL be returned

### Requirement: Model Detection Integration

The system SHALL use `Detector` class to determine model family and specific version for converter selection.

#### Scenario: Detect Claude 3.5 model
- **GIVEN** model name "claude-3.5-sonnet"
- **WHEN** `Detector.is_claude_model()` is called
- **THEN** result SHALL be True
- **WHEN** `Detector.is_claude_37_or_4()` is called
- **THEN** result SHALL be False
- **AND** protocol SHALL be ClaudeInvoke

#### Scenario: Detect Claude 3.7/4 model
- **GIVEN** model name "claude-4.5-sonnet"
- **WHEN** `Detector.is_claude_model()` is called
- **THEN** result SHALL be True
- **WHEN** `Detector.is_claude_37_or_4()` is called
- **THEN** result SHALL be True
- **AND** protocol SHALL be ClaudeConverse

#### Scenario: Detect Gemini model
- **GIVEN** model name "gemini-2.5-pro"
- **WHEN** `Detector.is_gemini_model()` is called
- **THEN** result SHALL be True
- **AND** protocol SHALL be GeminiGenerate

#### Scenario: Detect OpenAI/GPT model
- **GIVEN** model name "gpt-4o"
- **WHEN** `Detector.is_claude_model()` is called
- **THEN** result SHALL be False
- **WHEN** `Detector.is_gemini_model()` is called
- **THEN** result SHALL be False
- **AND** protocol SHALL be OpenAIChat

### Requirement: Converter Registry

The system SHALL provide a registry mapping model patterns to converter functions for extensibility.

#### Scenario: Register Claude 3.5 converter
- **GIVEN** a converter registry
- **WHEN** `register_converter()` is called for "claude-3.5-*" pattern
- **THEN** registry SHALL store mapping to ClaudeInvokeProtocol
- **AND** subsequent requests for "claude-3.5-sonnet" SHALL use registered converter

#### Scenario: Register Claude 3.7/4 converter
- **GIVEN** a converter registry
- **WHEN** `register_converter()` is called for "claude-3.7-*" pattern
- **THEN** registry SHALL store mapping to ClaudeConverseProtocol
- **AND** subsequent requests for "claude-4.5-sonnet" SHALL use registered converter

#### Scenario: Extend registry for new model
- **GIVEN** a converter registry
- **WHEN** a new model family "future-model-*" is registered
- **THEN** registry SHALL accept the new mapping
- **AND** routing SHALL use the new converter for matching models
- **AND** no code changes SHALL be required to `RequestRouter`
