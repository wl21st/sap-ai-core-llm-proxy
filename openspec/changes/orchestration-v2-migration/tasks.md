## 1. Dependency Migration

- [x] 1.1 Add `sap-ai-sdk-gen` to `pyproject.toml` and remove `generative-ai-hub-sdk`
- [x] 1.2 Run `uv sync` and verify the new SDK installs cleanly
- [x] 1.3 Verify `gen_ai_hub.orchestration_v2` imports are available in the new SDK

## 2. Config Schema Update

- [x] 2.1 Update `SubAccountConfig` Pydantic model in `config/config_parser.py` — add `orchestration_url: Optional[str]`, remove `deployment_ids` and `deployment_models` fields
- [x] 2.2 Add deprecation warnings when old fields (`deployment_ids`, `deployment_models`, `model_to_deployment_ids`, `model_to_deployment_urls`) are detected in config
- [x] 2.3 Update `ProxyConfig` to remove `model_to_deployment_urls` and related fields
- [x] 2.4 Update config loading to accept the new schema and validate that each subaccount has either `orchestration_url` or can auto-discover one
- [x] 2.5 Update example `config.json` / docs to reflect the new schema

## 3. Orchestration URL Auto-Discovery

- [x] 3.1 Update `_auto_discover_deployments` in `config/config_parser.py` to identify the orchestration service deployment (instead of per-model deployments)
- [x] 3.2 Store the discovered URL as `orchestration_url` on each `SubAccountConfig`
- [x] 3.3 Add a startup health check that verifies the `orchestration_url` is reachable

## 4. Foundation Model Discovery

- [x] 4.1 Create `utils/foundation_model_registry.py` with `FoundationModelRegistry` class
- [x] 4.2 Implement `fetch_models(subaccount)` — calls `GET /v2/lm/foundation-models` with Bearer token and `AI-Resource-Group` header
- [x] 4.3 Implement in-memory cache with 24h TTL and thread-safe access
- [x] 4.4 Implement static fallback model list (from the investigation doc's confirmed model list)
- [x] 4.5 Populate registry at startup across all configured subaccounts

## 5. Orchestration V2 Backend

- [x] 5.1 Create `utils/orchestration_client.py` with `OrchestrationClient` class
- [x] 5.2 Implement `build_request_body(model, messages, params)` — maps OpenAI fields to Orchestration V2 JSON format (`llm_module_config`, `templating_module_config`)
- [x] 5.3 Implement `invoke(subaccount, body)` — `POST {orchestration_url}/completion` non-streaming, returns OpenAI-compatible response dict
- [x] 5.4 Implement `invoke_stream(subaccount, body)` — `POST {orchestration_url}/completion` with `stream: true`, yields SSE chunks
- [x] 5.5 Add token injection (fetch from `TokenManager`) and `AI-Resource-Group` header
- [x] 5.6 Wrap with retry logic for HTTP 429 (reuse `@bedrock_retry` or equivalent)

## 6. Model Name Alias Resolution

- [x] 6.1 Create `utils/model_aliases.py` with default alias map (common aliases → canonical Orchestration V2 names)
- [x] 6.2 Implement `resolve_model_name(name, aliases)` function
- [x] 6.3 Load additional aliases from `config/aliases.json` if present (warn if missing, use defaults)
- [x] 6.4 Integrate alias resolution before Orchestration V2 dispatch

## 7. Proxy Request Routing Update

- [x] 7.1 Update `routers/chat.py` (or equivalent) to call `OrchestrationClient.invoke()` / `invoke_stream()` instead of the old model-specific endpoint dispatch
- [x] 7.2 Remove endpoint selection logic (`/converse`, `/invoke`, `/chat/completions` path selection) from `proxy_server.py`
- [x] 7.3 Update `/v1/models` endpoint to return data from `FoundationModelRegistry`
- [x] 7.4 Add model validation against `FoundationModelRegistry` before dispatch; return HTTP 404 for unknown models
- [x] 7.5 Update round-robin load balancing to cycle across subaccounts by `orchestration_url` (not deployment URLs)

## 8. Remove Deprecated Code

- [x] 8.1 Remove Bedrock-specific format converters from `proxy_helpers.py` — removed from main `/v1/chat/completions` path; provider-native handlers (`/openai/`, `/gemini/`) still use legacy converters for non-V2 subaccounts (deferred to a follow-on change)
- [x] 8.2 Remove model detection helpers from `proxy_helpers.py` — removed from all main routers (chat, messages, anthropic, gemini, openai, embeddings); handlers/streaming_generators.py still uses for legacy SSE path
- [x] 8.3 Remove `utils/sdk_pool.py` (Bedrock `ClientWrapper` pool)
- [x] 8.4 Remove `utils/sdk_utils.py` `fetch_all_deployments` and related Bedrock SDK utilities
- [x] 8.5 Remove per-model deployment URL resolution from `config/config_parser.py` (`_resolve_deployment_ids`, `_extract_deployment_ids_from_urls`)

## 9. Tests

- [x] 9.1 Update existing unit tests for `config/config_parser.py` to use new config schema
- [x] 9.2 Add unit tests for `OrchestrationClient.build_request_body` — parameter mapping
- [x] 9.3 Add unit tests for `FoundationModelRegistry` — fetch, cache TTL, static fallback
- [x] 9.4 Add unit tests for `resolve_model_name` alias resolution
- [x] 9.5 Update `routers/chat.py` tests to mock `OrchestrationClient`
- [x] 9.6 Run `make test` and fix any failures

## 10. Documentation and Validation

- [x] 10.1 Update `README.md` config example and migration notes (breaking config change)
- [x] 10.2 Run `make test-cov` and confirm coverage is maintained or improved
- [x] 10.3 Verify no references to removed fields or deprecated SDK remain in codebase
