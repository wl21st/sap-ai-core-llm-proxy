## Purpose

Establishes a standardized, categorized test hierarchy separating fast unit tests, local integration tests, and live API tests.

## ADDED Requirements

### Requirement: Standardized test taxonomy
The test suite SHALL categorize all test files into dedicated directories under `tests/`: `unit/`, `integration/`, and `api/`.

#### Scenario: Running unit tests only
- **WHEN** running unit tests via `pytest tests/unit` or `make test-unit`
- **THEN** only isolated, non-network unit tests execute quickly.

#### Scenario: Running integration tests
- **WHEN** running integration tests via `pytest tests/integration` or `make test-integration`
- **THEN** local server and client integration tests execute.

### Requirement: Full test coverage tracking across all subpackages
The test configuration SHALL measure code coverage across all package modules in `src/sap_ai_proxy/`, including routers, handlers, auth, config, and utils.

#### Scenario: Generating test coverage reports
- **WHEN** running `pytest --cov=sap_ai_proxy`
- **THEN** coverage is accurately calculated across all internal modules and reports missing lines.
