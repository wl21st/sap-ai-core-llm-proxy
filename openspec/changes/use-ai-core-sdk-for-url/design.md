# Design: SDK-based Deployment URL Lookup

## Architecture

The SAP AI Core LLM Proxy requires the full Deployment URL to forward requests (e.g., to `/v2/inference/deployments/{id}/...`).

Instead of static configuration, we introduce a **Discovery Phase** during `config_parser.py` loading:

1. **Input**: `config.json` contains `model_to_deployment_ids`.
2. **Process**:
    - Iterate through subaccounts.
    - For each Deployment ID, instantiate a temporary AI Core Client (using `ai_core_sdk.AICoreV2Client` or similar).
    - Call `deployment.get(id)`.
    - Extract `deployment_url`.
3. **Output**: Populate `SubAccountConfig.model_to_deployment_urls`.

## Technical Details

### SDK Usage

We need to determine the correct SDK class. Based on `pyproject.toml`, we have `sap-ai-sdk-gen`.
We likely need to use `ai_core_sdk.models.Deployment` or `ai_core_sdk.resource.Deployment`.

### Configuration Compatibility

To maintain backward compatibility:

- If `model_to_deployment_urls` is present (original format), use it.
- If `model_to_deployment_ids` is present (new format), resolve and add to URLs.
- Can support mixed usage.

### Error Handling

- Invalid Deployment ID: Log error and skip (or fail startup if strict).
- Network/Auth Failure: Retry or fail.

## Data Flow

`config.json` -> `load_proxy_config` -> `_resolve_deployment_ids` -> `SDK Call` -> `SubAccountConfig` -> `Proxy Server`
