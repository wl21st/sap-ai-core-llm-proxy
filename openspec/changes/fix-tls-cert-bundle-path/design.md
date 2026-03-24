## Context

The proxy uses the SAP AI SDK (`gen_ai_hub`) to authenticate with SAP AI Core. During token fetching, the SDK's `ai_api_client_sdk` library uses `requests` to make HTTPS calls. In uv-managed virtual environments, the `certifi` package may not be properly installed or its CA bundle path may become invalid when the cache is regenerated. This causes `requests.adapters` to fail during SSL verification with `OSError: Could not find a suitable TLS CA certificate bundle`.

Currently, the proxy catches this as an `AIAPIAuthenticatorException` with no context about the root cause, making debugging difficult. There are also no fallback mechanisms or configuration options for specifying alternate certificate paths.

## Goals / Non-Goals

**Goals:**
- Automatically detect and use system-level CA certificate bundles when `certifi` fails
- Allow configuration of custom CA certificate bundle paths via `config.json`
- Provide clear error messages distinguishing TLS certificate errors from authentication failures
- Ensure backward compatibility (no existing configurations should break)
- Gracefully handle SDK client initialization with certificate resolution

**Non-Goals:**
- Replace the SAP AI SDK's authentication mechanism
- Implement certificate pinning or custom validation logic beyond CA bundle resolution
- Handle non-HTTPS certificate errors (only focus on proxy → SAP AI Core communication)

## Decisions

### 1. CA Certificate Bundle Discovery Strategy
**Decision:** Implement a multi-level fallback chain for certificate resolution.

**Rationale:** Different environments have certificates in different locations. A fallback chain ensures robustness across uv, conda, venv, and system-level environments.

**Implementation order:**
1. Check config-specified path (if `ca_cert_bundle` in ProxyConfig)
2. Use `certifi.where()` (standard library fallback)
3. Check system paths: `/etc/ssl/certs/ca-bundle.crt` (Linux), `/usr/local/etc/openssl/cert.pem` (macOS), `%ALLUSERSPROFILE%\ssl\certs\ca-bundle.crt` (Windows)
4. Use `ssl.get_default_verify_paths()` from Python stdlib
5. If all fail, log warning but allow SDK to proceed (SDK may have its own fallback)

**Alternatives considered:**
- Ignore and let SDK handle it: Too opaque, hard to debug
- Fail fast if no CA bundle: Too restrictive, blocks legitimate use cases
- Pin to specific bundle: Too rigid, breaks in different environments

### 2. Configuration Extension
**Decision:** Add `ca_cert_bundle` field to ProxyConfig (in `config.json`).

**Rationale:** Gives users control without requiring code changes. Solves the problem at the source.

**Schema addition:**
```json
{
  "ca_cert_bundle": "/path/to/ca-bundle.crt",  // Optional, null by default
  "subaccounts": [...]
}
```

**Alternatives considered:**
- Environment variable only: Less discoverable, harder to manage in config files
- Hardcoded list: Not flexible for all environments

### 3. Where to Implement
**Decision:** Add certificate handling in three places:

1. **`config/config_parser.py`**: Add `ca_cert_bundle: Optional[str]` field to `ProxyConfig` Pydantic model
2. **`utils/sdk_pool.py`**: Add helper function `_resolve_ca_cert_bundle()` to discover certificates before SDK initialization
3. **`auth/token_manager.py`**: Pass resolved certificate path to `requests.Session` via `verify` parameter when fetching tokens

**Rationale:** This keeps certificate resolution logic centralized, applies to both SDK clients and direct HTTP calls, and is thread-safe.

**Alternatives considered:**
- Only in TokenManager: Would miss SDK client issues
- Only in sdk_pool.py: Wouldn't help with direct token fetch calls
- Global singleton: Harder to test and less flexible

### 4. Error Messaging
**Decision:** Catch `OSError` during token fetch and provide contextual error messages.

**Rationale:** Users need to know if it's a certificate issue, an authentication issue, or a network issue.

**Implementation:**
```python
try:
    token = fetch_token()
except OSError as e:
    if "CA certificate" in str(e) or "ssl" in str(e).lower():
        raise ProxyError(
            "TLS certificate error. Check ca_cert_bundle config or run: "
            "python -c 'import certifi; print(certifi.where())'"
        )
    raise
```

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| Multiple fallback paths could mask real misconfiguration | Log which path was used at INFO level; document in troubleshooting guide |
| Custom ca_cert_bundle path may be incorrect, causing hard-to-debug failures | Validate certificate path on startup; fail early with clear message |
| Changing SDK internals could break our certificate passing | Wrap SDK initialization in try-except; document SDK version compatibility |
| Performance overhead from repeated cert path discovery | Cache the resolved path in memory during proxy startup (one-time cost) |

## Migration Plan

1. **Code deployment**: Add config field, update TokenManager and sdk_pool with certificate resolution
2. **Backward compatibility**: No action needed for existing configs; fallback chain handles most cases
3. **Troubleshooting docs**: Add section to README explaining ca_cert_bundle config and how to diagnose certificate issues
4. **Monitoring**: Log ca_cert_bundle resolution at startup so we can see which path was used
