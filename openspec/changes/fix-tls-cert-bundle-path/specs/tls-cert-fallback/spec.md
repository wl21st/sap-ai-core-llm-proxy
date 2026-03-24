## ADDED Requirements

### Requirement: Automatic TLS CA certificate bundle discovery
The proxy SHALL automatically discover and resolve TLS CA certificate bundles when the environment's default bundle is missing or inaccessible, following a defined fallback chain.

#### Scenario: Use config-specified certificate path
- **WHEN** `ca_cert_bundle` is configured in `config.json`
- **THEN** the proxy SHALL use the specified path for all HTTPS connections

#### Scenario: Fallback to certifi when config not provided
- **WHEN** `ca_cert_bundle` is not configured and certifi is available
- **THEN** the proxy SHALL use `certifi.where()` to resolve the certificate bundle

#### Scenario: Fallback to system certificates when certifi unavailable
- **WHEN** `ca_cert_bundle` is not configured and certifi path is missing or invalid
- **THEN** the proxy SHALL check system paths (`/etc/ssl/certs/ca-bundle.crt`, `/usr/local/etc/openssl/cert.pem`, etc.) in order

#### Scenario: Use Python stdlib fallback
- **WHEN** config path, certifi, and system paths are all unavailable
- **THEN** the proxy SHALL use `ssl.get_default_verify_paths()` and proceed with execution

#### Scenario: Log which certificate bundle is used
- **WHEN** the proxy starts
- **THEN** the proxy SHALL log at INFO level the path to the CA certificate bundle being used

### Requirement: Validation of configured certificate paths
The proxy SHALL validate that custom CA certificate bundle paths exist and are readable at startup.

#### Scenario: Valid certificate path provided
- **WHEN** `ca_cert_bundle` in config points to a valid, readable file
- **THEN** the proxy SHALL proceed with normal operation

#### Scenario: Invalid certificate path provided
- **WHEN** `ca_cert_bundle` in config points to a missing or unreadable file
- **THEN** the proxy SHALL fail at startup with a clear error message indicating the invalid path

## ADDED Requirements

### Requirement: Pass certificate bundle to SDK clients and HTTP requests
The proxy SHALL ensure all HTTPS connections (both SDK clients and direct requests) use the resolved CA certificate bundle.

#### Scenario: Token fetch uses certificate bundle
- **WHEN** the token manager fetches a token from SAP AI Core
- **THEN** the HTTPS request SHALL use the resolved CA certificate bundle

#### Scenario: SDK client uses certificate bundle
- **WHEN** the SDK client makes requests to SAP AI Core
- **THEN** the request SHALL use the resolved CA certificate bundle for SSL verification
