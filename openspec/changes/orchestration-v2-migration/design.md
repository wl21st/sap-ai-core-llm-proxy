## Context

The proxy currently operates on a per-model-deployment model: at startup it enumerates all running deployments from `GET /v2/lm/deployments`, builds a `model_name → deployment_url` mapping, and routes each inference request to the specific deployment URL with a model-specific path (`/converse`, `/invoke`, `/chat/completions`, etc.). This requires users to maintain individual deployments for every model they want to use and keep those deployment IDs in config.

SAP has replaced this with the Orchestration V2 service (`sap-ai-sdk-gen >= 6.7.0`): one orchestration deployment serves all foundation models. The previous SDK (`generative-ai-hub-sdk`) is archived as of May 2025. The new inference endpoint accepts a model name in the request body and returns OpenAI-compatible JSON natively, eliminating the need for per-model format converters.

Key existing code locations:
- `utils/sdk_pool.py` — Bedrock `ClientWrapper` pool (to be replaced)
- `utils/sdk_utils.py` — `fetch_all_deployments` (to be replaced)
- `config/config_parser.py` — `SubAccountConfig`, `_auto_discover_deployments` (to be updated)
- `proxy_helpers.py` — model detection + format converters (to be removed)
- `proxy_server.py` / `routers/` — endpoint selection, streaming paths (to be simplified)

## Goals / Non-Goals

**Goals:**
- Migrate inference path to SAP Orchestration V2 (`POST {orchestration_url}/completion`)
- Replace `generative-ai-hub-sdk` with `sap-ai-sdk-gen`
- Simplify config: replace per-model `deployment_ids` with a single `orchestration_url` per subaccount
- Serve available models from `GET /v2/lm/foundation-models` at the `/v1/models` endpoint
- Preserve the existing OpenAI-compatible API surface for proxy consumers (no client-side breaking changes beyond model name normalization)
- Support both streaming and non-streaming inference through orchestration V2

**Non-Goals:**
- Supporting Orchestration V1 (deprecated)
- Migrating embedding endpoints (separate concern; Orchestration V2 supports embeddings but this change focuses on LLM chat completions)
- Preserving backward-compatibility for the config JSON format (a migration guide will be provided)
- Supporting models not available through the Orchestration V2 service (e.g., self-hosted models)

## Decisions

### Decision 1: Use `sap-ai-sdk-gen` `OrchestrationService` via HTTP (not the Python SDK abstraction)

**Choice**: Call `POST {orchestration_url}/completion` directly via `requests`/`httpx`, rather than using `OrchestrationService.run()` / `OrchestrationService.stream()`.

**Rationale**: The proxy already manages its own token caching, retry logic, and streaming SSE handling. Using the SDK's high-level abstractions would conflict with these. Direct HTTP calls give full control over headers, streaming, and error handling, and avoid the SDK's template placeholder mechanism (`{{?user_query}}`) which is unnecessary — we pass messages directly.

**Alternative considered**: Use `OrchestrationService` — rejected because it wraps the response and requires fitting into its template model, losing flexibility.

### Decision 2: Single orchestration URL per subaccount (no per-model routing)

**Choice**: Each subaccount config has one `orchestration_url` (the running orchestration deployment URL). All models are dispatched to this URL with `model_name` in the request body.

**Rationale**: This matches the Orchestration V2 architecture exactly. Round-robin load balancing across subaccounts is preserved; within a subaccount there is only one orchestration endpoint (no per-deployment round-robin needed).

**Alternative considered**: Maintain per-model deployment URLs alongside orchestration URL for backward compat — rejected, adds complexity and the whole point is simplification.

### Decision 3: Remove format converters; pass messages directly

**Choice**: Since Orchestration V2 accepts and returns OpenAI-compatible JSON, the `proxy_helpers.py` converters (`convert_claude37_to_openai`, `convert_claude_to_openai`, `convert_gemini_to_openai`) are removed. The proxy forwards the OpenAI-format request body (messages, temperature, max_tokens, etc.) by mapping fields to the `llm_module_config` and `templating_module_config` in the orchestration request.

**Rationale**: Eliminates a large maintenance surface. The converters were the source of most bugs and model-specific edge cases.

**Alternative considered**: Keep converters as fallback — rejected; the orchestration service normalizes this server-side.

### Decision 4: Request body mapping — OpenAI → Orchestration V2

The proxy will translate an incoming OpenAI-format request:
```json
{
  "model": "gpt-4o",
  "messages": [...],
  "max_tokens": 512,
  "temperature": 0.7,
  "stream": false
}
```
into the Orchestration V2 body:
```json
{
  "orchestration_config": {
    "module_configurations": {
      "llm_module_config": {
        "model_name": "gpt-4o",
        "model_params": {
          "max_tokens": 512,
          "temperature": 0.7
        }
      },
      "templating_module_config": {
        "template": [
          {"role": "system", "content": "..."},
          {"role": "user", "content": "..."}
        ]
      }
    }
  },
  "stream": false
}
```
The response is already OpenAI-compatible and can be forwarded with minimal transformation.

### Decision 5: Model discovery — `GET /v2/lm/foundation-models` with startup cache

**Choice**: At startup (or on first `/v1/models` request), call `GET /v2/lm/foundation-models` for each subaccount, union the results, and cache in memory. Refresh on a configurable interval (default 24h) or on restart.

**Alternative considered**: Static model list hardcoded from the investigation doc — acceptable fallback if the API is unavailable, but dynamic discovery is preferred.

### Decision 6: Config schema migration

New `SubAccountConfig` shape:
```json
{
  "name": "my-subaccount",
  "client_id": "...",
  "client_secret": "...",
  "auth_url": "...",
  "base_url": "...",
  "resource_group": "default",
  "orchestration_url": "https://api.ai.{region}.cfapps.sap.hana.ondemand.com/v2/inference/deployments/{id}/completion"
}
```
Fields removed: `deployment_ids`, `model_to_deployment_urls`, `deployment_url`.

## Risks / Trade-offs

- **[Risk] Orchestration V2 availability** — The orchestration service deployment must be running in each subaccount before the proxy can serve requests. → Mitigation: Add a startup health check that verifies the orchestration URL is reachable; fail fast with a clear error message.

- **[Risk] Model name normalization** — Current clients may send normalized names (e.g., `claude-3-sonnet`) that differ from Orchestration V2 model names (e.g., `anthropic--claude-3.5-sonnet`). → Mitigation: Keep a thin model name alias map (replacing the existing `normalize_model_names` function) that maps common aliases to canonical Orchestration V2 names.

- **[Risk] Streaming SSE format differences** — Orchestration V2 streaming SSE may differ subtly from what clients expect. → Mitigation: Integration test the streaming path against the orchestration endpoint before removing old converters.

- **[Risk] Config migration friction** — Breaking config change for existing users. → Mitigation: Provide a migration guide in CHANGELOG / README; print a clear error if old config fields are detected.

- **[Trade-off] Remove Bedrock client pool** — `utils/sdk_pool.py` is removed. Any future need to use Bedrock directly (not via orchestration) would require reimplementing it. Acceptable given the architectural direction toward orchestration.

## Migration Plan

1. Add `sap-ai-sdk-gen` to `pyproject.toml`; remove `generative-ai-hub-sdk`
2. Implement new config schema (`orchestration_url` per subaccount) with Pydantic validation
3. Implement `OrchestrationBackend` — HTTP client for `POST {orchestration_url}/completion` (non-streaming + streaming)
4. Implement `FoundationModelDiscovery` — fetches `GET /v2/lm/foundation-models` per subaccount
5. Wire new backend into `proxy_server.py` / `routers/chat.py`, replacing old dispatch logic
6. Update `/v1/models` endpoint to use `FoundationModelDiscovery`
7. Remove `proxy_helpers.py` converters and `utils/sdk_pool.py`
8. Update `config/config_parser.py` — new Pydantic models, remove `_auto_discover_deployments`
9. Update tests; add integration test for orchestration backend

**Rollback**: The change is self-contained. Reverting the branch restores the old behavior. No database migrations required.

## Open Questions

- Should the proxy support **both** the old deployment-based routing and the new orchestration path simultaneously (feature flag), or is a hard cutover acceptable? → Recommend hard cutover given the SDK deprecation.
- What is the exact streaming SSE format returned by Orchestration V2 — does it match OpenAI's `data: {...}\n\n` format exactly, or does it need a thin adapter? → Needs verification against a live orchestration endpoint.
- Should `orchestration_url` be auto-discovered at startup (by calling `GET /v2/lm/deployments` filtered to orchestration service configs), or must it be explicitly provided in config? → Both options should be supported: explicit URL takes priority; auto-discovery as fallback.
