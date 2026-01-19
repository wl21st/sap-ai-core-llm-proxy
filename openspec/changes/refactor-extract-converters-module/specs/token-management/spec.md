# Spec: Token Management

## MODIFIED Requirements

### Requirement: Token Usage Extraction

The system SHALL provide unified extraction of token usage from various AI provider response formats.

#### Scenario: Extract tokens from OpenAI response
- **GIVEN** an OpenAI API response with usage data
- **WHEN** `TokenExtractor.from_openai_response()` is called
- **THEN** a `TokenUsage` dataclass SHALL be returned
- **AND** prompt_tokens SHALL be extracted from usage.prompt_tokens
- **AND** completion_tokens SHALL be extracted from usage.completion_tokens
- **AND** total_tokens SHALL be extracted from usage.total_tokens
- **AND** default value 0 SHALL be used if fields are missing
- **AND** the TokenUsage SHALL have to_openai_format() method returning dict

#### Scenario: Extract tokens from Claude response
- **GIVEN** a Claude API response with usage data
- **WHEN** `TokenExtractor.from_claude_response()` is called
- **THEN** a `TokenUsage` dataclass SHALL be returned
- **AND** prompt_tokens SHALL be extracted from usage.input_tokens
- **AND** completion_tokens SHALL be extracted from usage.output_tokens
- **AND** total_tokens SHALL be calculated as prompt + completion
- **AND** default value 0 SHALL be used if fields are missing
- **AND** the TokenUsage SHALL have to_claude_format() method returning dict

#### Scenario: Extract tokens from Claude 3.7/4 streaming metadata
- **GIVEN** a Claude 3.7/4 streaming response with usage metadata chunk
- **WHEN** `TokenExtractor.from_claude37_metadata()` is called
- **THEN** a `TokenUsage` dataclass SHALL be returned
- **AND** prompt_tokens SHALL be extracted from usage.inputTokens
- **AND** completion_tokens SHALL be extracted from usage.outputTokens
- **AND** total_tokens SHALL be extracted from usage.totalTokens
- **AND** default value 0 SHALL be used if fields are missing

#### Scenario: Extract tokens from Gemini usage metadata
- **GIVEN** a Gemini API response with usageMetadata
- **WHEN** `TokenExtractor.from_gemini_usage_metadata()` is called
- **THEN** a `TokenUsage` dataclass SHALL be returned
- **AND** prompt_tokens SHALL be extracted from usageMetadata.promptTokenCount
- **AND** completion_tokens SHALL be extracted from usageMetadata.candidatesTokenCount
- **AND** total_tokens SHALL be extracted from usageMetadata.totalTokenCount
- **AND** default value 0 SHALL be used if fields are missing

### Requirement: Token Usage Representation

The system SHALL provide a unified dataclass representation of token usage across all providers.

#### Scenario: Create TokenUsage dataclass
- **GIVEN** prompt_tokens=100, completion_tokens=50, total_tokens=150, cached_tokens=0
- **WHEN** a TokenUsage instance is created
- **THEN** all fields SHALL be initialized with the given values
- **AND** default value 0 SHALL be used for optional fields
- **AND** the instance SHALL be immutable or have clear mutability semantics

#### Scenario: Convert TokenUsage to OpenAI format
- **GIVEN** a TokenUsage instance with all fields set
- **WHEN** `to_openai_format()` is called
- **THEN** a dict SHALL be returned with OpenAI usage format
- **AND** the dict SHALL contain "prompt_tokens", "completion_tokens", "total_tokens"
- **AND** values SHALL match the TokenUsage fields
- **AND** cached_tokens SHALL NOT be included (not part of OpenAI format)

#### Scenario: Convert TokenUsage to Claude format
- **GIVEN** a TokenUsage instance with all fields set
- **WHEN** `to_claude_format()` is called
- **THEN** a dict SHALL be returned with Claude usage format
- **AND** the dict SHALL contain "input_tokens", "output_tokens"
- **AND** input_tokens SHALL match prompt_tokens
- **AND** output_tokens SHALL match completion_tokens
- **AND** cached_tokens SHALL NOT be included (not part of Claude format)

### Requirement: Token Usage Logging

The system SHALL log token usage for monitoring and billing purposes.

#### Scenario: Log token usage from non-streaming responses
- **GIVEN** a non-streaming response with token usage
- **WHEN** token usage is extracted
- **THEN** the usage SHALL be logged at INFO level
- **AND** the log SHALL include model name
- **AND** the log SHALL include prompt_tokens, completion_tokens, total_tokens
- **AND** the log SHALL include subaccount name for cost tracking

#### Scenario: Log token usage from streaming responses
- **GIVEN** a streaming response with final usage metadata
- **WHEN** the stream completes and usage is extracted
- **THEN** the usage SHALL be logged at INFO level
- **AND** the log SHALL include model name
- **AND** the log SHALL include all token counts
- **AND** the log SHALL include streaming duration

#### Scenario: Log cached token usage for Claude 3.7/4
- **GIVEN** a Claude 3.7/4 response with cached_read_tokens
- **WHEN** token usage is extracted
- **THEN** cached_read_tokens SHALL be logged separately
- **AND** the log SHALL indicate cache hit
- **AND** effective cost SHALL be calculated considering cached tokens

## ADDED Requirements

### Requirement: Reasoning Token Configuration

The system SHALL handle thinking/reasoning token configuration for models that support it.

#### Scenario: Adjust max_tokens for Claude thinking budget
- **GIVEN** a Claude request with thinking.budget_tokens=1000
- **WHEN** `ReasoningConfig.adjust_for_claude()` is called
- **THEN** max_tokens SHALL be adjusted if <= budget_tokens
- **AND** max_tokens SHALL be set to budget_tokens + 1 if missing or too small
- **AND** the adjustment SHALL be logged with INFO level
- **AND** existing max_tokens > budget_tokens SHALL be preserved
- **AND** the adjusted body SHALL be returned

#### Scenario: Remove unsupported thinking fields
- **GIVEN** a Claude request with thinking config containing "context_management"
- **WHEN** `ReasoningConfig.adjust_for_claude()` is called
- **THEN** "context_management" SHALL be removed from thinking config
- **AND** the removal SHALL be logged with INFO level
- **AND** other thinking fields SHALL be preserved

#### Scenario: Pass through reasoning_effort for OpenAI models
- **GIVEN** an OpenAI request with reasoning_effort="medium"
- **WHEN** `ReasoningConfig.passthrough_reasoning_effort()` is called
- **THEN** reasoning_effort SHALL be copied to target payload
- **AND** the field SHALL not be modified
- **AND** if reasoning_effort is not present, nothing SHALL be added
- **AND** the modified target_payload SHALL be returned

#### Scenario: Handle missing thinking config
- **GIVEN** a request without thinking field
- **WHEN** `ReasoningConfig.adjust_for_claude()` is called
- **THEN** the request SHALL be returned unchanged
- **AND** no adjustments SHALL be made
- **AND** no errors SHALL be raised

### Requirement: Token Usage Caching Support

The system SHALL support cached token tracking for Claude 3.7/4 models.

#### Scenario: Track cached tokens in TokenUsage
- **GIVEN** a Claude 3.7/4 response with cached_read_tokens=500
- **WHEN** TokenUsage is created
- **THEN** cached_tokens field SHALL be set to 500
- **AND** cached_tokens SHALL default to 0 if not provided
- **AND** the field SHALL be accessible for reporting

#### Scenario: Calculate effective cost with cached tokens
- **GIVEN** TokenUsage with prompt_tokens=1000, cached_tokens=500
- **WHEN** effective cost is calculated
- **THEN** billable prompt tokens SHALL be prompt_tokens - cached_tokens = 500
- **AND** cached_tokens SHALL be excluded from cost calculation
- **AND** completion_tokens SHALL be fully counted
