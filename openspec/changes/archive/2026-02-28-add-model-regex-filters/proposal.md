## Why

Currently, the proxy silently loads all models from the config.json deployment_models section without any filtering capability. This makes it difficult to control which models are exposed through the API, especially when managing large deployments or wanting to selectively enable/disable models based on patterns.

## What Changes

- Add optional `model_filters` configuration section to `config.json` with support for inclusive and exclusive regex patterns
- Implement model filtering logic during config parsing that applies regex patterns to model IDs
- Models matching exclusive patterns will be filtered out, models matching inclusive patterns will be kept (if inclusive list is specified)
- If no filters are specified, behavior remains unchanged (all models loaded)
- Add validation to ensure regex patterns are valid during config loading
- Log filtered models at startup for visibility into what models are being excluded/included

## Capabilities

### New Capabilities
- `model-filtering`: Configuration-based filtering of model IDs using inclusive/exclusive regex patterns applied during config parsing

### Modified Capabilities
- `model-resolution`: Model resolution logic must respect filtered models from config - models filtered out should behave as if they were never configured

## Impact

- **Config Schema**: `config.json` gets new optional `model_filters` section with `include` and `exclude` regex lists
- **Config Module**: `config/proxy_config.py` and related config classes need to parse and validate filter configuration
- **Model Loading**: Config parsing logic must apply filters to deployment_models before building internal model registry
- **Model Resolution**: `proxy_server.py` model resolution logic must work with pre-filtered model lists
- **Logging**: Startup logs should show which models were filtered and why
- **Backwards Compatibility**: No breaking changes - filters are optional, absence preserves current behavior
