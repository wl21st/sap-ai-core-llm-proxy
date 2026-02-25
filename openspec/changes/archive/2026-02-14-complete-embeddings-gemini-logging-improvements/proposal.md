## Why

The proxy server has three small but important gaps: embeddings requests without an explicit model will fail ungracefully, Gemini-2.5-pro's new streaming format isn't handled, and the utility script uses `print()` instead of logging. Closing these gaps improves robustness, extends model support, and maintains code hygiene.

## What Changes

- Add fallback model detection for embeddings requests when no explicit model is specified
- Implement handling for Gemini-2.5-pro's JSON-structured streaming wire format in the streaming response generator
- Refactor `inspect_deployments.py` to use the logger for all output instead of `print()` statements

## Capabilities

### New Capabilities
- `embeddings-fallback-model`: Default model selection for embeddings when not specified
- `gemini-2.5-pro-streaming`: Support for Gemini-2.5-pro's distinct streaming format

### Modified Capabilities
- `inspect-deployments-output`: Now uses structured logging instead of print statements

## Impact

- `proxy_server.py`: Add default model logic to `handle_embedding_service_call()`
- `handlers/streaming_generators.py`: Add Gemini-2.5-pro format detection and conversion
- `inspect_deployments.py`: Replace `print()` with `logger.info()`
