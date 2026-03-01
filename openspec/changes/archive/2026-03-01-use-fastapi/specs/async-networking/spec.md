## ADDED Requirements

### Requirement: Async HTTP Client
The application SHALL use `httpx.AsyncClient` for all backend network requests, replacing synchronous `requests` calls.

#### Scenario: Async Backend Request
- **WHEN** the proxy forwards a request to a backend service
- **THEN** it SHALL await the response using `httpx`
- **AND** it SHALL NOT block the event loop

### Requirement: Async Streaming Generator
The application SHALL implement streaming response generation using Python asynchronous generators (`async def`, `yield`).

#### Scenario: Streaming Response
- **WHEN** a streaming request is processed
- **THEN** the generator SHALL iterate over upstream chunks asynchronously (`async for chunk in response.aiter_lines()`)
- **AND** it SHALL apply transformations to each chunk without blocking
- **AND** it SHALL yield transformed chunks to the client

### Requirement: Async Bedrock Integration
The application SHALL execute AWS Bedrock SDK calls in a thread pool to prevent blocking the async event loop, as `boto3` is synchronous.

#### Scenario: Bedrock Invocation
- **WHEN** a request is routed to Bedrock
- **THEN** the SDK call SHALL be wrapped in `fastapi.concurrency.run_in_threadpool` or equivalent
