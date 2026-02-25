## ADDED Requirements

### Requirement: Gemini-2.5-pro Streaming Format Support

The proxy SHALL detect and convert Gemini-2.5-pro's distinct streaming JSON format to OpenAI-compatible SSE format.

#### Scenario: Gemini-2.5-pro streaming response detected

- **WHEN** a streaming response from Gemini-2.5-pro arrives with the format: `{candidates: [{content: {parts: [{text: ...}]}}]}`
- **THEN** the system SHALL recognize this as Gemini-2.5-pro's format
- **AND** SHALL convert it to OpenAI streaming format with proper `data:` prefixes and newlines

#### Scenario: Standard Gemini streaming response (fallback)

- **WHEN** a streaming response arrives in the standard Gemini `{candidates: [...], usageMetadata: {...}}` format
- **THEN** the system SHALL continue using the existing converter
- **AND** no errors SHALL occur

#### Scenario: Streaming conversion includes usage metadata

- **WHEN** Gemini-2.5-pro streaming concludes
- **THEN** the final chunk SHALL include proper token usage information
- **AND** the format SHALL match OpenAI's `usage` field structure
