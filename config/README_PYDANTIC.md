# Pydantic Configuration System

This document describes the alternative Pydantic-based configuration system for the SAP AI Core LLM Proxy.

## Overview

The Pydantic configuration system provides an alternative to the existing dataclass-based configuration with the following benefits:

- **Automatic Validation**: Pydantic v2 validates all configuration data on load
- **Type Safety**: Full type hints and runtime type checking
- **Better Error Messages**: Clear validation error messages for misconfiguration
- **Serialization**: Easy conversion to/from JSON with `model_dump()` and model construction
- **Constraints**: Field-level constraints (e.g., port range validation, required fields)
- **Extensibility**: Easy to add validators and custom field logic

## Files

### `config/pydantic_models.py`
Contains the Pydantic BaseModel definitions:

- **`ServiceKeyModel`**: SAP AI Core service key credentials with field aliases for snake_case conversion
- **`TokenInfoModel`**: Token information for caching and thread-safety
- **`SubAccountConfigModel`**: Configuration for a single subaccount with optional service key and token info
- **`ProxyConfigModel`**: Main configuration model with subaccounts, port, host, and model mappings

### `config/pydantic_loader.py`
Contains loader functions for working with Pydantic models:

- **`load_pydantic_config(file_path)`**: Load and validate configuration from JSON
- **`load_pydantic_config_with_service_keys(config_file_path, service_keys_dir)`**: Load config with service key resolution
- **`config_to_json(config, file_path)`**: Serialize configuration to JSON file
- **`validate_config_dict(config_dict)`**: Validate a config dictionary without full instantiation

## Configuration Structure

The JSON configuration file should follow this structure:

```json
{
  "subAccounts": {
    "subAccountName": {
      "resource_group": "default",
      "service_key_json": "path/to/service_key.json",
      "deployment_models": {
        "model-name": ["https://deployment-url-1", "https://deployment-url-2"]
      }
    }
  },
  "secret_authentication_tokens": ["token1", "token2"],
  "port": 3001,
  "host": "127.0.0.1"
}
```

### Field Details

#### SubAccountConfig Fields

- `resource_group` (string, optional): SAP AI Core resource group (default: "default")
- `service_key_json` (string, required): Path to the service key JSON file
- `deployment_models` (object, optional): Mapping of model names to deployment URLs

#### ProxyConfig Fields

- `subAccounts` (object, required): Dictionary of subaccount configurations
- `secret_authentication_tokens` (array, optional): List of valid authentication tokens
- `port` (integer, optional): Port number (default: 3001, range: 1-65535)
- `host` (string, optional): Host address (default: "127.0.0.1")

## Usage Examples

### Basic Loading

```python
from config.pydantic_loader import load_pydantic_config

# Load configuration from file
config = load_pydantic_config("config.json")

# Access configuration
print(f"Port: {config.port}")
print(f"Host: {config.host}")
print(f"Subaccounts: {list(config.subAccounts.keys())}")

# Access subaccount configuration
subaccount = config.subAccounts["subAccount1"]
print(f"Service key file: {subaccount.service_key_json}")
print(f"Deployment models: {list(subaccount.deployment_models.keys())}")
```

### Loading with Service Keys

```python
from config.pydantic_loader import load_pydantic_config_with_service_keys

# Load configuration and service keys
config = load_pydantic_config_with_service_keys(
    "config.json",
    service_keys_dir="/path/to/keys"
)

# Service keys are now loaded
for name, subaccount in config.subAccounts.items():
    if subaccount.service_key:
        print(f"{name}: {subaccount.service_key.client_id}")
```

### Initialization and Model Mapping

```python
config = load_pydantic_config("config.json")

# Initialize configuration (builds model mappings)
config.initialize()

# Access global model to subaccount mapping
for model_name, subaccount_list in config.model_to_subaccounts.items():
    print(f"{model_name}: {subaccount_list}")
```

### Serialization

```python
from config.pydantic_loader import config_to_json

config = load_pydantic_config("config.json")

# Save to new file
config_to_json(config, "config_backup.json")
```

### Validation

```python
from config.pydantic_loader import validate_config_dict
import json

# Validate a dictionary without full instantiation
with open("config.json") as f:
    config_dict = json.load(f)

try:
    validate_config_dict(config_dict)
    print("Configuration is valid")
except ValueError as e:
    print(f"Validation failed: {e}")
```

## Field Aliases and Type Mapping

The `ServiceKeyModel` uses Pydantic field aliases to map SAP service key field names:

| Python Field | JSON/Alias |
|--------------|-----------|
| `client_id` | `clientid` |
| `client_secret` | `clientsecret` |
| `auth_url` | `url` |
| `identity_zone_id` | `identityzoneid` |

This allows seamless loading of SAP service key files without manual conversion.

## Validation Features

### Required Fields

- `subAccounts[*].service_key_json`: Required for each subaccount
- `subAccounts[*].deployment_models`: Required (can be empty dict)

### Constraints

- `port`: Must be between 1 and 65535
- All string fields must be non-empty when provided

### Optional Fields

- `secret_authentication_tokens`: Defaults to empty list
- `resource_group`: Defaults to "default"
- `port`: Defaults to 3001
- `host`: Defaults to "127.0.0.1"

## Error Handling

Pydantic provides detailed error messages for validation failures:

```python
try:
    config = load_pydantic_config("config.json")
except FileNotFoundError as e:
    print(f"Configuration file not found: {e}")
except ValueError as e:
    print(f"Configuration validation failed: {e}")
    # e.g., "1 validation error for ProxyConfigModel
    #        port
    #        Input should be less than or equal to 65535"
```

## Migration from Dataclass-based System

The existing dataclass-based system in `config/models.py` and `config/loader.py` remains unchanged. The Pydantic system is an alternative that can be used alongside it:

```python
# Old system (still available)
from config.config_parser import load_proxy_config

config = load_proxy_config("config.json")

# New system (Pydantic-based)
from config.pydantic_loader import load_pydantic_config

config = load_pydantic_config("config.json")
```

Both systems can coexist, allowing for gradual migration if needed.

## Testing

Run the test suite to verify the Pydantic configuration system:

```bash
cd /path/to/sap-ai-core-llm-proxy
source .venv/bin/activate
python test_pydantic_config.py
```

Expected output: All 6 tests pass
- Load Config
- Initialize Config
- Serialize Config
- Validation
- Invalid Config Detection
- Port Range Validation

## Performance Considerations

- **Validation Overhead**: Pydantic validation adds minimal overhead during config load (happens once at startup)
- **Memory**: Pydantic models have slightly higher memory overhead than dataclasses, but negligible for typical config sizes
- **Type Checking**: Runtime type validation ensures configuration consistency

## Future Enhancements

Potential improvements to the Pydantic system:

1. Add custom validators for URL format validation
2. Add support for environment variable substitution
3. Add configuration hot-reloading support
4. Add JSON schema generation for documentation
5. Add encrypted service key file support
