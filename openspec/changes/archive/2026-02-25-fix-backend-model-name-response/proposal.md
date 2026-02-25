## Why

The current configuration process is error-prone and redundant. Users must manually map model names to deployment IDs in `config.json`, even though the SAP AI Core backend already knows which model is running. This leads to "wrong" mappings and unnecessary maintenance.

## What Changes

- **Auto-Discovery**: The proxy will automatically fetch *all* deployments for configured subaccounts at startup.
- **Backend Model Identification**: It will rely on `details.resources.backend_details.model.name` from the API response to identify the model.
- **Smart Aliasing**: The system will automatically apply aliases to raw backend model names (e.g., mapping `anthropic--claude-4.5-sonnet` to `sonnet-4.5`, `claude-4.5-sonnet`).
- **Config Simplification**: Users no longer *need* to list specific deployment IDs in `config.json` unless they want to restrict/pin specific ones. The `deployment_ids` section becomes optional.
- **CLI Tool**: The inspection CLI remains as a debugging tool but is no longer required for basic setup.

## Capabilities

### New Capabilities
- `auto-discovery`: Logic to fetch and register all available deployments at startup without explicit ID configuration.
- `model-aliasing`: A registry or configuration of aliases (e.g., `anthropic--claude-3.5-sonnet` → `sonnet-3.5`) to make model names user-friendly.

### Modified Capabilities
- `config-loading`: Update `config_parser.py` to support "wildcard" or "all" deployment loading for a subaccount.
- `sdk-integration`: Enhance SDK wrappers to return the full model details for auto-discovery.

## Impact

- **Configuration**: Drastically simplifies `config.json`.
- **Startup Time**: Slight increase to fetch all deployments (negligible for most use cases).
- **Robustness**: Eliminates model-mismatch configuration errors.
