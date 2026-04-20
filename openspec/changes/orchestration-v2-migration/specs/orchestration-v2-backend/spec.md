## ADDED Requirements

### Requirement: Orchestration V2 Inference Dispatch
The system SHALL route all LLM chat completion inference requests through the SAP Orchestration V2 endpoint (`POST {orchestration_url}/completion`) for each configured subaccount, passing the model name in the request body instead of selecting a model-specific deployment URL.

#### Scenario: Non-streaming inference request
- **WHEN** a client sends `POST /v1/chat/completions` with `model: "gpt-4o"` and `stream: false`
- **THEN** the proxy constructs an Orchestration V2 request body with `llm_module_config.model_name: "gpt-4o"` and `templating_module_config.template` populated from the messages array
- **AND** the proxy sends `POST {orchestration_url}/completion` with the request body and a valid Bearer token
- **AND** the proxy forwards the OpenAI-compatible response body to the client with HTTP 200

#### Scenario: Streaming inference request
- **WHEN** a client sends `POST /v1/chat/completions` with `model: "gemini-2.5-flash"` and `stream: true`
- **THEN** the proxy constructs an Orchestration V2 request body with `stream: true` at the root level
- **AND** the proxy sends `POST {orchestration_url}/completion` and forwards the SSE response as `text/event-stream` to the client
- **AND** each SSE chunk is forwarded as-is (Orchestration V2 returns OpenAI-compatible SSE)

### Requirement: OpenAI-to-Orchestration Request Mapping
The system SHALL map OpenAI-format request fields to the Orchestration V2 request body format, translating `messages`, `max_tokens`, `temperature`, and other standard parameters to their Orchestration V2 equivalents.

#### Scenario: Parameter mapping
- **WHEN** a client sends a request with `max_tokens: 512`, `temperature: 0.7`, and a messages array
- **THEN** `max_tokens` is mapped to `llm_module_config.model_params.max_tokens`
- **AND** `temperature` is mapped to `llm_module_config.model_params.temperature`
- **AND** the messages array is placed in `templating_module_config.template` preserving `role` and `content`

### Requirement: Round-Robin Load Balancing Across Subaccounts
The system SHALL select the target subaccount for each request using round-robin load balancing, distributing load evenly across all configured subaccounts.

#### Scenario: Multiple subaccounts configured
- **WHEN** three subaccounts are configured and requests arrive sequentially
- **THEN** requests are distributed in round-robin order across the three `orchestration_url` values
- **AND** each subaccount's token is fetched and cached independently

### Requirement: Model Name Alias Resolution
The system SHALL resolve common model name aliases to canonical Orchestration V2 model names before dispatching the request.

#### Scenario: Alias resolution before dispatch
- **WHEN** a client sends a request with `model: "claude-3.5-sonnet"`
- **THEN** the system resolves this to `anthropic--claude-3.5-sonnet`
- **AND** the Orchestration V2 request uses the canonical name

#### Scenario: Unknown model name passed through
- **WHEN** a client sends a request with `model: "gpt-4o"` (already canonical)
- **THEN** the model name is passed through unchanged to the Orchestration V2 request

### Requirement: Error Handling and Retry
The system SHALL handle errors from the Orchestration V2 endpoint, retrying on rate limit responses (HTTP 429) with exponential backoff, and returning appropriate error responses to the client for other failures.

#### Scenario: Rate limit retry
- **WHEN** the orchestration endpoint returns HTTP 429
- **THEN** the proxy retries up to 4 times with exponential backoff (4s to 16s)
- **AND** if all retries fail, the proxy returns HTTP 429 to the client

#### Scenario: Non-retryable error
- **WHEN** the orchestration endpoint returns HTTP 400 or HTTP 500
- **THEN** the proxy returns the error response to the client immediately without retrying
