## MODIFIED Requirements

### Requirement: External Alias Configuration
The system SHALL load model aliases from a configurable source (JSON file or inline config), mapping user-provided model names to canonical Orchestration V2 model names (e.g., `"claude-3.5-sonnet"` → `"anthropic--claude-3.5-sonnet"`).

#### Scenario: Valid alias file
- **WHEN** the proxy starts and `config/aliases.json` exists
- **THEN** it loads the mapping and uses it to resolve model names before Orchestration V2 dispatch

#### Scenario: Missing alias file
- **WHEN** `config/aliases.json` is missing
- **THEN** the system logs a warning and proceeds with a built-in default alias map

## REMOVED Requirements

### Requirement: Deployment Caching
**Reason**: Per-model deployment caching (7-day TTL disk cache) is no longer needed because the Orchestration V2 architecture uses a single `orchestration_url` per subaccount. Model availability is now tracked via the in-memory foundation model registry (24h TTL) from the `foundation-model-discovery` capability.
**Migration**: Remove any `--no-cache` / `--refresh` flags related to deployment caching. Model registry refresh is automatic via TTL.

## ADDED Requirements

### Requirement: Orchestration URL Config Field
The system SHALL accept an `orchestration_url` field in each subaccount configuration block. This field specifies the URL of the running Orchestration V2 deployment for that subaccount.

#### Scenario: Valid orchestration URL in config
- **WHEN** the proxy loads a config with `orchestration_url: "https://..."` for a subaccount
- **THEN** it uses that URL for all Orchestration V2 inference requests for that subaccount

#### Scenario: Missing orchestration URL triggers auto-discovery
- **WHEN** the proxy loads a config without `orchestration_url` for a subaccount
- **THEN** it attempts auto-discovery via `GET /v2/lm/deployments` to find the orchestration service deployment
- **AND** if discovery fails, it logs an error and the subaccount is unavailable for inference

### Requirement: Removed Config Fields
The system SHALL reject or warn on deprecated config fields (`deployment_ids`, `deployment_models`, `model_to_deployment_ids`, `model_to_deployment_urls`) with a clear migration message.

#### Scenario: Deprecated fields detected at startup
- **WHEN** a config file contains `deployment_ids` or `deployment_models`
- **THEN** the proxy logs a deprecation warning specifying which fields to remove and what to add instead
- **AND** the proxy proceeds with a best-effort parse (ignoring deprecated fields) rather than failing hard
