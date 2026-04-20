## 1. Dependency Migration

- [ ] 1.1 Add `sap-ai-sdk-gen` to `pyproject.toml` and remove `generative-ai-hub-sdk`
- [ ] 1.2 Run `uv sync` and verify the new SDK installs cleanly
- [ ] 1.3 Verify `gen_ai_hub.orchestration_v2` imports are available in the new SDK

## 2. Config Schema Update

- [ ] 2.1 Update `SubAccountConfig` Pydantic model in `config/config_parser.py` — add `orchestration_url: Optional[str]`, remove `deployment_ids` and `deployment_models` fields
- [ ] 2.2 Add deprecation warnings when old fields (`deployment_ids`, `deployment_models`, `model_to_deployment_ids`, `model_to_deployment_urls`) are detected in config
- [ ] 2.3 Update `ProxyConfig` to remove `model_to_deployment_urls` and related fields
- [ ] 2.4 Update config loading to accept the new schema and validate that each subaccount has either `orchestration_url` or can auto-discover one
- [ ] 2.5 Update example `config.json` / docs to reflect the new schema

## 3. Orchestration URL Auto-Discovery

- [ ] 3.1 Update `_auto_discover_deployments` in `config/config_parser.py` to identify the orchestration service deployment (instead of per-model deployments)
- [ ] 3.2 Store the discovered URL as `orchestration_url` on each `SubAccountConfig`
- [ ] 3.3 Add a startup health check that verifies the `orchestration_url` is reachable

## 4. Foundation Model Discovery

- [ ] 4.1 Create `utils/foundation_model_registry.py` with `FoundationModelRegistry` class
- [ ] 4.2 Implement `fetch_models(subaccount)` — calls `GET /v2/lm/foundation-models` with Bearer token and `AI-Resource-Group` header
- [ ] 4.3 Implement in-memory cache with 24h TTL and thread-safe access
- [ ] 4.4 Implement static fallback model list (from the investigation doc's confirmed model list)
- [ ] 4.5 Populate registry at startup across all configured subaccounts

## 5. Orchestration V2 Backend

- [ ] 5.1 Create `utils/orchestration_client.py` with `OrchestrationClient` class
- [ ] 5.2 Implement `build_request_body(model, messages, params)` — maps OpenAI fields to Orchestration V2 JSON format (`llm_module_config`, `templating_module_config`)
- [ ] 5.3 Implement `invoke(subaccount, body)` — `POST {orchestration_url}/completion` non-streaming, returns OpenAI-compatible response dict
- [ ] 5.4 Implement `invoke_stream(subaccount, body)` — `POST {orchestration_url}/completion` with `stream: true`, yields SSE chunks
- [ ] 5.5 Add token injection (fetch from `TokenManager`) and `AI-Resource-Group` header
- [ ] 5.6 Wrap with retry logic for HTTP 429 (reuse `@bedrock_retry` or equivalent)

## 6. Model Name Alias Resolution

- [ ] 6.1 Create `utils/model_aliases.py` with default alias map (common aliases → canonical Orchestration V2 names)
- [ ] 6.2 Implement `resolve_model_name(name, aliases)` function
- [ ] 6.3 Load additional aliases from `config/aliases.json` if present (warn if missing, use defaults)
- [ ] 6.4 Integrate alias resolution before Orchestration V2 dispatch

## 7. Proxy Request Routing Update

- [ ] 7.1 Update `routers/chat.py` (or equivalent) to call `OrchestrationClient.invoke()` / `invoke_stream()` instead of the old model-specific endpoint dispatch
- [ ] 7.2 Remove endpoint selection logic (`/converse`, `/invoke`, `/chat/completions` path selection) from `proxy_server.py`
- [ ] 7.3 Update `/v1/models` endpoint to return data from `FoundationModelRegistry`
- [ ] 7.4 Add model validation against `FoundationModelRegistry` before dispatch; return HTTP 404 for unknown models
- [ ] 7.5 Update round-robin load balancing to cycle across subaccounts by `orchestration_url` (not deployment URLs)

## 8. Remove Deprecated Code

- [ ] 8.1 Remove Bedrock-specific format converters from `proxy_helpers.py` (`convert_claude37_to_openai`, `convert_claude_to_openai`, `convert_gemini_to_openai`, etc.)
- [ ] 8.2 Remove model detection helpers from `proxy_helpers.py` (`is_claude_37_or_4`, `is_claude_model`, `is_gemini_model`, etc.) — no longer needed for routing
- [ ] 8.3 Remove `utils/sdk_pool.py` (Bedrock `ClientWrapper` pool)
- [ ] 8.4 Remove `utils/sdk_utils.py` `fetch_all_deployments` and related Bedrock SDK utilities
- [ ] 8.5 Remove per-model deployment URL resolution from `config/config_parser.py` (`_resolve_deployment_ids`, `_extract_deployment_ids_from_urls`)

## 9. Tests

- [ ] 9.1 Update existing unit tests for `config/config_parser.py` to use new config schema
- [ ] 9.2 Add unit tests for `OrchestrationClient.build_request_body` — parameter mapping
- [ ] 9.3 Add unit tests for `FoundationModelRegistry` — fetch, cache TTL, static fallback
- [ ] 9.4 Add unit tests for `resolve_model_name` alias resolution
- [ ] 9.5 Update `routers/chat.py` tests to mock `OrchestrationClient`
- [ ] 9.6 Run `make test` and fix any failures

## 10. Documentation and Validation

- [ ] 10.1 Update `README.md` config example and migration notes (breaking config change)
- [ ] 10.2 Run `make test-cov` and confirm coverage is maintained or improved
- [ ] 10.3 Verify no references to removed fields or deprecated SDK remain in codebase
