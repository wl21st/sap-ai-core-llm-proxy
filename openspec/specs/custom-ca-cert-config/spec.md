# Capability: Custom CA Certificate Configuration

## Purpose

Allow users to provide a custom CA certificate bundle path for outbound HTTPS connections.

## Requirements

### Requirement: Optional custom CA certificate bundle configuration
The proxy SHALL accept an optional `ca_cert_bundle` field in `config.json` to allow users to specify a custom CA certificate bundle path.

#### Scenario: Configuration with certificate path
- **WHEN** user adds `"ca_cert_bundle": "/path/to/ca-bundle.crt"` to `config.json`
- **THEN** the proxy SHALL use the specified path for all HTTPS connections

#### Scenario: Configuration without certificate path
- **WHEN** user does not include `ca_cert_bundle` in `config.json`
- **THEN** the proxy SHALL follow the automatic discovery fallback chain

### Requirement: ProxyConfig includes CA certificate bundle field
The `ProxyConfig` Pydantic model SHALL include an optional `ca_cert_bundle` field.

#### Scenario: Parse configuration with ca_cert_bundle
- **WHEN** `config.json` contains a valid `ca_cert_bundle` path
- **THEN** `ProxyConfig` SHALL successfully parse and store the value

#### Scenario: Parse configuration without ca_cert_bundle
- **WHEN** `config.json` does not include `ca_cert_bundle`
- **THEN** `ProxyConfig` SHALL set `ca_cert_bundle` to `None` by default
