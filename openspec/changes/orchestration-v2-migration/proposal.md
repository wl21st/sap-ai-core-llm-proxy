## Why

The current proxy relies on per-model deployments, requiring each model to be individually deployed and tracked by deployment URL. SAP has introduced the Orchestration V2 API (`gen_ai_hub.orchestration_v2`) which eliminates this requirement — a single orchestration service deployment serves all models by name, and the old `generative-ai-hub-sdk` is now deprecated (archived as of May 2025). Migrating to the new SDK (`sap-ai-sdk-gen`) and Orchestration V2 is necessary to maintain a supported, modern integration and to drastically simplify the proxy's model routing complexity.

## What Changes

- Replace `generative-ai-hub-sdk` dependency with `sap-ai-sdk-gen` (active, v6.7.0+)
- Replace per-model deployment discovery (`GET /v2/lm/deployments`) with foundation model enumeration (`GET /v2/lm/foundation-models`) or static model list
- Replace per-model deployment URL routing with a single orchestration service endpoint (`POST {orchestration_url}/completion`)
- Eliminate `model_to_deployment_urls` and `deployment_ids` from subaccount config — replaced with a single `orchestration_url` per subaccount
- Remove or greatly simplify `proxy_helpers.py` format converters — Orchestration V2 returns OpenAI-compatible JSON natively
- Remove Bedrock-specific SDK client pool (`utils/sdk_pool.py`) and endpoint selection logic (`/converse`, `/invoke`, etc.)
- **BREAKING**: Config JSON schema changes — existing `deployment_ids` and per-model deployment config fields are replaced by `orchestration_url`
- Add new `GET /v1/models` response based on `GET /v2/lm/foundation-models` or a static model registry

## Capabilities

### New Capabilities
- `orchestration-v2-backend`: Routes all LLM inference through the SAP Orchestration V2 endpoint (`{orchestration_url}/completion`) with per-subaccount round-robin load balancing
- `foundation-model-discovery`: Discovers and serves the list of available models via `GET /v2/lm/foundation-models` per subaccount, replacing deployment-based model discovery

### Modified Capabilities
- `model-resolution`: Model resolution changes from deployment URL lookup to passing model name directly in the Orchestration V2 request body — requirement changes from "resolve model → deployment URL" to "validate model name → pass through"
- `auto-discovery`: Auto-discovery changes from enumerating per-model deployments to discovering the single orchestration service deployment URL per subaccount
- `deployment-lookup`: Deployment lookup is no longer needed for model routing — this capability is replaced by `orchestration-v2-backend`
- `caching-and-config`: Config schema changes — `deployment_ids`/`model_to_deployment_urls` fields removed, `orchestration_url` added per subaccount

## Impact

- **proxy_server.py**: Remove Bedrock/Gemini/Claude-specific endpoint selection; replace with single orchestration dispatch path; update `/v1/models` endpoint
- **proxy_helpers.py**: Most format converters (`convert_claude37_to_openai`, `convert_gemini_to_openai`, etc.) become unnecessary; remove or stub out; keep OpenAI-passthrough logic
- **config/config_parser.py**: Update `SubAccountConfig` and `ProxyConfig` Pydantic models; update `_auto_discover_deployments` to find orchestration deployment
- **utils/sdk_pool.py**: Remove or repurpose — Bedrock client pool no longer needed; replace with `OrchestrationService` client pool
- **pyproject.toml / uv.lock**: Replace `generative-ai-hub-sdk` with `sap-ai-sdk-gen`
- **Breaking config change**: Users must update `config.json` to remove per-model deployment IDs and add `orchestration_url`
