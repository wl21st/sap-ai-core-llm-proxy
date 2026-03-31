## Context

The proxy currently supports two ways to configure model→deployment mappings per subaccount:

1. **`deployment_models`** (direct URLs in config.json) — static, must be updated manually as models are added
2. **`model_to_deployment_ids`** (deployment IDs in config.json) — resolved to URLs at startup via `fetch_deployment_url()` in `utils/sdk_utils.py`

SAP AI Core exposes a `/v2/lm/deployments` API that returns all deployments for a resource group. `fetch_all_deployments()` already calls this API and returns `{id, url, model_name, created_at}` records (with `model_name` extracted from `backend_details.model.name`). The `inspect_deployments.py` CLI tool already uses this to print deployment tables.

**Gap**: `fetch_all_deployments()` currently only extracts `backend_details.model.name` (works for model-serving deployments). Orchestration deployments (`scenario_id: orchestration`) do not have this field; instead their model identity comes from `configuration_name`. Neither is wired into startup auto-population of `model_to_deployment_urls`.

**Startup hook**: `main.py` → `lifespan()` calls `load_proxy_config()` then `ProxyGlobalContext.initialize(config)`. The right place to inject discovery is after `load_proxy_config()`, before `context.initialize(config)`.

## Goals / Non-Goals

**Goals:**
- At startup, for each subaccount with `auto_discover: true` (or with no `deployment_models`), call `fetch_all_deployments()` and merge results into `model_to_deployment_urls`
- Support orchestration-scenario deployments: extract model name from `configuration_name` when `backend_details.model.name` is absent
- Merge strategy: manually configured URLs take precedence over discovered ones for the same model key
- No new external dependencies

**Non-Goals:**
- Periodic refresh / hot-reload during proxy lifetime (startup-only for now)
- Filtering discovered deployments by `scenario_id` (all RUNNING deployments are included)
- Writing discovered URLs back to config.json on disk

## Decisions

### Decision 1: Model name extraction for orchestration deployments

**Problem**: Orchestration deployments (`scenario_id: orchestration`) lack `backend_details.model.name`.

**Choice**: Fall back to `configuration_name` when `backend_details.model.name` is absent. This is the only stable, human-readable identifier present on orchestration deployments (as seen in the user's sample: `"configuration_name": "ail-auto-orchestration"`).

**Alternative considered**: Use `deployment_id` as model name. Rejected — IDs are opaque and don't map to user-facing model names.

**Where**: Extend the existing model-name extraction logic inside `fetch_all_deployments()` in `utils/sdk_utils.py`.

### Decision 2: Trigger for auto-discovery

**Problem**: When should discovery run vs. manual config?

**Choice**: Add an optional `auto_discover: bool` field to `SubAccountConfig`. Default is `False` when `deployment_models` is provided (preserving backward compatibility), and effectively treated as `True` when `deployment_models` is absent and `model_to_deployment_ids` is also absent. Explicit `auto_discover: true` always triggers discovery even when manual mappings are present.

**Alternative considered**: Always run discovery for all subaccounts. Rejected — unnecessary API calls at startup for fully-configured deployments, and could overwrite manual overrides.

### Decision 3: Merge strategy

**Problem**: How to merge discovered and manual URLs for the same model key?

**Choice**: Manual `deployment_models` URLs are authoritative and always win. Discovered URLs for the same model key are appended if not already in the list; discovered URLs for new model keys are added as new entries.

**Rationale**: Manual config is the human override path; auto-discovery fills gaps only.

### Decision 4: Discovery placement in startup

**Problem**: Where in the startup sequence to inject discovery?

**Choice**: Inside `lifespan()` in `main.py`, after `load_proxy_config()` but before `context.initialize(config)`. Create a new `run_discovery(config: ProxyConfig)` function in a new `discovery.py` module that mutates `SubAccountConfig.model_to_deployment_urls` in-place.

**Alternative considered**: Inside `config_parser.py`. Rejected — config parsing should remain synchronous and network-free for testability.

## Risks / Trade-offs

- **Startup latency**: Discovery adds one API call per subaccount. With 10 deployments and low latency this is ~1-2s. Mitigation: `fetch_all_deployments()` already has disk caching (7-day TTL); discovery reuses it, so only the first startup after cache expiry is slow.
- **Network failure at startup**: If discovery fails for a subaccount, the proxy should log a warning and continue with whatever manual config exists — not crash. Mitigation: wrap discovery in try/except per subaccount.
- **`configuration_name` uniqueness**: If two orchestration deployments share the same `configuration_name`, the second URL is appended to the list (list-valued, so both are available for load balancing). No conflict.
- **Stale cached discovery**: 7-day disk cache means new deployments appear only after cache expires or `force_refresh=True`. Mitigation: document this; a future refresh endpoint can be added.

## Migration Plan

1. No config changes required for existing deployments — `auto_discover` defaults to `false`
2. Operators who want auto-discovery add `"auto_discover": true` to their subaccount config
3. Operators who have no `deployment_models` and no `model_to_deployment_ids` automatically get discovery (progressive enhancement)
4. Rollback: remove `auto_discover: true` from config and restart

## Open Questions

- Should there be a `/v1/admin/refresh-deployments` endpoint to force re-discovery without restart? (Out of scope for this change — tracked separately.)
- Should discovery be parallelized across subaccounts for faster startup? (Low priority; most deployments have 1-2 subaccounts.)
