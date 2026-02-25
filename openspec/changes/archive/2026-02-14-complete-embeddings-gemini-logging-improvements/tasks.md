## 1. Embeddings Default Model

- [x] 1.1 Add default model resolution logic to `handle_embedding_service_call()` in `proxy_server.py`
- [x] 1.2 Handle the case when no model is provided and no default is available (raise ValueError)
- [x] 1.3 Verify existing tests still pass with the change
- [x] 1.4 Test manually: call embeddings endpoint without explicit model

## 2. Gemini-2.5-pro Streaming Format

- [x] 2.1 Add format detection helper `is_gemini_2_5_pro_format()` in `handlers/streaming_generators.py`
- [x] 2.2 Implement conversion logic for Gemini-2.5-pro format to OpenAI SSE
- [x] 2.3 Update streaming handler to detect and route Gemini-2.5-pro responses
- [x] 2.4 Verify integration test for Gemini-2.5-pro streaming passes
- [x] 2.5 Ensure standard Gemini format still works (backward compatibility)

## 3. Logging Refactor (inspect_deployments.py)

- [x] 3.1 Replace `print(f"\n--- Subaccount: {name} ---")` with `logger.info()`
- [x] 3.2 Replace `print(f"Resource Group: ...")` with `logger.info()`
- [x] 3.3 Replace `print("  No deployments found.")` with `logger.info()`
- [x] 3.4 Replace table header and divider prints with `logger.info()`
- [x] 3.5 Replace deployment data prints with `logger.info()`
- [x] 3.6 Replace "Loading configuration" print with `logger.info()`
- [x] 3.7 Replace "Found N subaccounts" print with `logger.info()`
- [x] 3.8 Test: Run `python inspect_deployments.py` and verify output format is identical

## 4. Verify

- [x] 4.1 Run full test suite: `make test`
- [x] 4.2 No new type errors or warnings
- [x] 4.3 Git diff shows only intended changes
