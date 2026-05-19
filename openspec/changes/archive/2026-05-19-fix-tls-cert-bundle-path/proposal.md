## Why

The SAP AI Core LLM Proxy fails to authenticate with SAP AI Core when using certain Python/uv environments. The root cause is a missing or inaccessible TLS CA certificate bundle (`certifi/cacert.pem`) in the uv-managed virtual environment. When the SDK attempts to fetch authentication tokens, the `requests` library fails with `OSError: Could not find a suitable TLS CA certificate bundle`, cascading into `AIAPIAuthenticatorException`. This blocks all proxy operations that require token authentication.

## What Changes

- Implement automatic TLS CA certificate bundle discovery and fallback mechanisms
- Add SDK client initialization with explicit certificate handling
- Improve error messages to distinguish TLS issues from authentication failures
- Add configuration option to specify custom CA certificate bundle path
- Document troubleshooting steps for certificate-related errors

## Capabilities

### New Capabilities

- `tls-cert-fallback`: Automatic discovery and fallback for CA certificate bundles when environment bundles are missing or inaccessible
- `custom-ca-cert-config`: Configuration option to specify custom CA certificate bundle path for SDK clients

### Modified Capabilities

- `token-fetching`: Enhanced with explicit CA certificate handling to prevent failures when `certifi` is unavailable or misconfigured

## Impact

- **Files affected**: `proxy_server.py`, `auth/token_manager.py`, `utils/sdk_pool.py`, `config/config_parser.py`
- **Dependencies**: `requests`, `certifi`, `gen_ai_hub` SDK
- **Breaking changes**: None (backward compatible with existing configurations)
- **SDK behavior**: Improved robustness; SDK clients will now handle certificate resolution more gracefully
