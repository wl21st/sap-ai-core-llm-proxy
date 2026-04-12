## ADDED Requirements

### Requirement: Stream parameter defaults to non-streaming
The proxy SHALL default the `stream` parameter to `false` when it is absent from the request body, in accordance with the Anthropic Messages API and OpenAI Chat Completions API specifications.

#### Scenario: Messages endpoint omits stream parameter
- **WHEN** a POST request to `/v1/messages` does not include a `stream` field
- **THEN** the proxy SHALL invoke the non-streaming Bedrock backend (`invoke_bedrock_non_streaming`) and return a synchronous JSON response

#### Scenario: Messages endpoint explicitly sets stream to false
- **WHEN** a POST request to `/v1/messages` includes `"stream": false`
- **THEN** the proxy SHALL invoke the non-streaming Bedrock backend and return a synchronous JSON response

#### Scenario: Messages endpoint explicitly sets stream to true
- **WHEN** a POST request to `/v1/messages` includes `"stream": true`
- **THEN** the proxy SHALL invoke the streaming Bedrock backend and return an SSE response (behavior unchanged)

#### Scenario: Claude model handler omits stream parameter
- **WHEN** `handle_claude_request()` receives a payload without a `stream` field
- **THEN** the handler SHALL route to the non-streaming endpoint (`/converse` for Claude 3.7/4, `/invoke` for older models)

#### Scenario: Claude model handler receives stream false
- **WHEN** `handle_claude_request()` receives a payload with `"stream": false`
- **THEN** the handler SHALL route to the non-streaming endpoint
