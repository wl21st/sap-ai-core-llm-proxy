## ADDED Requirements

### Requirement: External Alias Configuration
The system SHALL load model aliases from a JSON file (`config/aliases.json`).

#### Scenario: Valid alias file
- **WHEN** the proxy starts and `config/aliases.json` exists
- **THEN** it loads the mapping and uses it for model aliasing

#### Scenario: Missing alias file
- **WHEN** `config/aliases.json` is missing
- **THEN** the system logs a warning and proceeds with default/empty aliases

### Requirement: Deployment Caching
The system SHALL cache the results of deployment fetching to disk.

#### Scenario: Cache hit
- **WHEN** fetching deployments for a service key + resource group that was fetched recently (within 7 days)
- **THEN** the system returns the cached list without making an API call

#### Scenario: Cache miss/expiration
- **WHEN** fetching deployments for the first time OR after cache expiry
- **THEN** the system calls the SAP AI Core API and updates the cache

#### Scenario: Force refresh
- **WHEN** the user provides a `--no-cache` or `--refresh` flag (implementation detail)
- **THEN** the cache is bypassed/updated
