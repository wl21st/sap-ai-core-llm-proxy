## ADDED Requirements

### Requirement: Embeddings Default Model Fallback

The system SHALL select a sensible default model when an embeddings request is made without an explicit model, rather than failing.

#### Scenario: Request without explicit model

- **WHEN** a request to `/v1/embeddings` is made without specifying a `model` field
- **THEN** the system SHALL use a default model from the proxy configuration
- **AND** the embeddings endpoint SHALL be called successfully with the default model

#### Scenario: Request with explicit model

- **WHEN** a request to `/v1/embeddings` is made with an explicit `model` field
- **THEN** the system SHALL use the specified model
- **AND** the default model SHALL NOT be applied

#### Scenario: No default model configured

- **WHEN** a request without explicit model is made and no default is configured
- **THEN** the system SHALL return a clear error message indicating a model must be specified
- **AND** the HTTP status code SHALL be 400 (Bad Request)
