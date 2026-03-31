## Why

The proxy currently requires operators to manually list `deployment_models` URLs in `config.json` for every subaccount. As teams deploy new models via SAP AI Core (both standard Bedrock models and orchestration-scenario deployments), the config becomes stale and requires manual updates. The SAP AI Core Deployments API provides the authoritative list of running deployments in real time — the proxy should use it.

## What Changes

- The proxy MAY query the SAP AI Core Deployments API at startup for each subaccount where `deployment_models` is absent or where `auto_discover: true` is set.
- Discovery fetches all RUNNING deployments (not limited to `scenario_id: orchestration` — both orchestration and model-serving deployments are included).
- Discovered deployment URLs are merged with any manually configured `deployment_models` entries; manual entries take precedence for the same model name.
- Model names are extracted from the deployment's `configuration_name` or `backend_details.model.name` (whichever is available), with alias support.
- The existing `auto-discovery` spec is extended to cover orchestration deployments explicitly and to specify the merge behaviour with manual config.

## Capabilities

### New Capabilities

- `orchestration-model-loading`: Calls the SAP AI Core Deployments API (`/v2/lm/deployments`) at proxy startup, filters to RUNNING status, and registers each deployment's URL under its model name — covering both orchestration and non-orchestration scenarios.

### Modified Capabilities

- `auto-discovery`: Extend existing requirements to (1) include orchestration-scenario deployments alongside model-serving deployments, and (2) define merge precedence: manually configured URLs always override auto-discovered ones for the same model key.

## Impact

- **`config/`**: `SubAccountConfig` gains optional `auto_discover: bool` flag (default `false` for backward compatibility when `deployment_models` is present; effectively `true` when `deployment_models` is absent).
- **`proxy_server.py`** startup logic: add post-config-load step that calls the discovery routine and merges results.
- **`auth/` / SDK utilities**: reuse existing `TokenManager` to authenticate the discovery API call; extend SDK helper to parse the deployments list response.
- **No breaking changes**: existing `deployment_models`-only configs continue to work unchanged.
- **New dependency**: none required; uses the same SAP AI Core REST API already accessed for inference.
