# Spec: Request Routing

## ADDED Requirements

### Requirement: Unified Request Router

The system SHALL provide a unified request router that orchestrates model detection, load balancing, protocol selection, and endpoint construction.

#### Scenario: Route Claude 3.5 request
- **GIVEN** an OpenAI-format request with model "claude-3.5-sonnet"
- **WHEN** `RequestRouter.route()` is called
- **THEN** model SHALL be detected as Claude 3.5
- **AND** protocol SHALL be selected as "ClaudeInvoke"
- **AND** load balancer SHALL select a subaccount and deployment URL
- **AND** endpoint path SHALL be `/invoke` or `/invoke-with-response-stream`
- **AND** request SHALL be converted using `convert_openai_to_claude`
- **AND** router SHALL return (endpoint_url, modified_payload, subaccount_name, protocol)

#### Scenario: Route Claude 3.7/4 request
- **GIVEN** an OpenAI-format request with model "claude-4.5-sonnet"
- **WHEN** `RequestRouter.route()` is called
- **THEN** model SHALL be detected as Claude 3.7/4
- **AND** protocol SHALL be selected as "ClaudeConverse"
- **AND** load balancer SHALL select a subaccount and deployment URL
- **AND** endpoint path SHALL be `/converse` or `/converse-stream`
- **AND** request SHALL be converted using `convert_openai_to_claude37`
- **AND** router SHALL return (endpoint_url, modified_payload, subaccount_name, protocol)

#### Scenario: Route Gemini request
- **GIVEN** an OpenAI-format request with model "gemini-2.5-pro"
- **WHEN** `RequestRouter.route()` is called
- **THEN** model SHALL be detected as Gemini
- **AND** protocol SHALL be selected as "GeminiGenerate"
- **AND** load balancer SHALL select a subaccount and deployment URL
- **AND** endpoint path SHALL be `/models/{model}:generateContent` or `/models/{model}:streamGenerateContent`
- **AND** request SHALL be converted using `convert_openai_to_gemini`
- **AND** router SHALL return (endpoint_url, modified_payload, subaccount_name, protocol)

#### Scenario: Route OpenAI request
- **GIVEN** an OpenAI-format request with model "gpt-4o"
- **WHEN** `RequestRouter.route()` is called
- **THEN** model SHALL be detected as OpenAI/GPT
- **AND** protocol SHALL be selected as "OpenAIChat"
- **AND** load balancer SHALL select a subaccount and deployment URL
- **AND** endpoint path SHALL be `/chat/completions`
- **AND** request SHALL pass through with minimal normalization
- **AND** router SHALL return (endpoint_url, modified_payload, subaccount_name, protocol)

### Requirement: Endpoint Path Construction

The system SHALL construct endpoint URLs dynamically based on model type, streaming flag, and protocol.

#### Scenario: Non-streaming Claude 3.5 endpoint
- **GIVEN** a base URL "https://api.example.com"
- **AND** model "claude-3.5-sonnet" with stream=False
- **WHEN** endpoint is constructed for ClaudeInvoke protocol
- **THEN** endpoint SHALL be "https://api.example.com/invoke"

#### Scenario: Streaming Claude 3.5 endpoint
- **GIVEN** a base URL "https://api.example.com"
- **AND** model "claude-3.5-sonnet" with stream=True
- **WHEN** endpoint is constructed for ClaudeInvoke protocol
- **THEN** endpoint SHALL be "https://api.example.com/invoke-with-response-stream"

#### Scenario: Non-streaming Claude 3.7/4 endpoint
- **GIVEN** a base URL "https://api.example.com"
- **AND** model "claude-4.5-sonnet" with stream=False
- **WHEN** endpoint is constructed for ClaudeConverse protocol
- **THEN** endpoint SHALL be "https://api.example.com/converse"

#### Scenario: Streaming Claude 3.7/4 endpoint
- **GIVEN** a base URL "https://api.example.com"
- **AND** model "claude-4.5-sonnet" with stream=True
- **WHEN** endpoint is constructed for ClaudeConverse protocol
- **THEN** endpoint SHALL be "https://api.example.com/converse-stream"

#### Scenario: Non-streaming Gemini endpoint
- **GIVEN** a base URL "https://api.example.com"
- **AND** model "gemini-2.5-pro" with stream=False
- **WHEN** endpoint is constructed for GeminiGenerate protocol
- **THEN** endpoint SHALL be "https://api.example.com/models/gemini-2.5-pro:generateContent"

#### Scenario: Streaming Gemini endpoint
- **GIVEN** a base URL "https://api.example.com"
- **AND** model "gemini-2.5-pro" with stream=True
- **WHEN** endpoint is constructed for GeminiGenerate protocol
- **THEN** endpoint SHALL be "https://api.example.com/models/gemini-2.5-pro:streamGenerateContent"

#### Scenario: OpenAI endpoint with API version
- **GIVEN** a base URL "https://api.example.com"
- **AND** model "gpt-4o"
- **WHEN** endpoint is constructed for OpenAIChat protocol
- **THEN** endpoint SHALL include API version parameter
- **AND** endpoint SHALL be "https://api.example.com/chat/completions?api-version=2023-05-15"

#### Scenario: OpenAI endpoint with new API version
- **GIVEN** a base URL "https://api.example.com"
- **AND** model "gpt-o3-mini" (requires new API version)
- **WHEN** endpoint is constructed for OpenAIChat protocol
- **THEN** endpoint SHALL use 2024-12-01-preview API version
- **AND** endpoint SHALL be "https://api.example.com/chat/completions?api-version=2024-12-01-preview"

### Requirement: Routing Decision Logging

The system SHALL log all routing decisions for debugging and monitoring.

#### Scenario: Log successful routing
- **GIVEN** a request for model "claude-3.5-sonnet"
- **WHEN** routing completes successfully
- **THEN** router SHALL log selected model
- **AND** router SHALL log selected protocol
- **AND** router SHALL log selected subaccount
- **AND** router SHALL log constructed endpoint URL
- **AND** logs SHALL include trace ID for correlation

#### Scenario: Log routing with fallback
- **GIVEN** a request for model "claude-3.7-opus" which triggers fallback
- **WHEN** routing completes with fallback model
- **THEN** router SHALL log original requested model
- **AND** router SHALL log fallback model used
- **AND** router SHALL log reason for fallback

#### Scenario: Log routing error
- **GIVEN** a request for model "unknown-model" which is not deployed
- **WHEN** routing fails with no fallback available
- **THEN** router SHALL log error with model name
- **AND** router SHALL log attempted fallbacks
- **AND** router SHALL log error at ERROR level
