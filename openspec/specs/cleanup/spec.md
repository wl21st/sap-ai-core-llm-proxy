# Cleanup Specification

## Purpose
Tracking the removal of deprecated assets and maintenance of project hygiene.
## Requirements
### Requirement: Deprecate Legacy Entry Point
The legacy entry point `proxy_server.py` SHALL emit a warning to users upon execution.

#### Scenario: Warn on Legacy Usage
- **Given** the `proxy_server.py` file is executed
- **When** the application starts
- **Then** a warning should be logged stating that `proxy_server.py` is deprecated and recommending `sap-ai-proxy` (via `main.py`)

### Requirement: No orphaned production functions
Production code SHALL NOT contain functions that are never called from any production or test code, where the function has no documented purpose as a public API or test utility.

#### Scenario: get_counters removed from load_balancer
- **WHEN** `load_balancer.py` is read
- **THEN** `get_counters()` does not exist (confirmed never called in production or tests)

#### Scenario: sync streaming generator removed from streaming_generators
- **WHEN** `handlers/streaming_generators.py` is read
- **THEN** `generate_bedrock_streaming_response_sync()` does not exist (only the async variant is used)

### Requirement: No unused imports in production code
The codebase SHALL contain no unused import statements in production files as reported by `ruff check --select F401,F811`.

#### Scenario: Ruff F401/F811 clean on production files
- **WHEN** `ruff check . --select F401,F811` is run excluding test directories
- **THEN** zero violations are reported

### Requirement: No unused imports in test code
The test suite SHALL contain no unused import statements as reported by `ruff check --select F401,F811`.

#### Scenario: Ruff F401/F811 clean on test files
- **WHEN** `ruff check . --select F401,F811` is run on the `tests/` directory
- **THEN** zero violations are reported

### Requirement: No unused local variables in test code
Test files SHALL contain no local variable assignments that are never read, as reported by `ruff check --select F841`.

#### Scenario: Ruff F841 clean on test files
- **WHEN** `ruff check . --select F841` is run on the `tests/` directory
- **THEN** zero violations are reported

### Requirement: Test suite stays green after cleanup
All existing tests SHALL pass after dead code removal.

#### Scenario: Test suite passes post-cleanup
- **WHEN** `make test` is run after all removals
- **THEN** all tests pass with no new failures

### Requirement: Unit API tests cover cleaned routes
New unit tests SHALL verify that route handlers for `/v1/chat/completions`, `/v1/messages`, and `/v1/models` return expected HTTP status codes after cleanup.

#### Scenario: Chat completions route responds correctly
- **WHEN** a unit test posts a minimal valid request to `/v1/chat/completions` with mocked backend
- **THEN** the response status is 200 and the response body contains `choices`

#### Scenario: Messages route responds correctly
- **WHEN** a unit test posts a minimal valid request to `/v1/messages` with mocked backend
- **THEN** the response status is 200 and the response body contains `content`

#### Scenario: Models route responds correctly
- **WHEN** a unit test sends GET `/v1/models` with mocked config
- **THEN** the response status is 200 and the response body contains `data`

### Requirement: Integration smoke tests confirm end-to-end behavior
Integration smoke tests SHALL verify that the three primary API routes respond without error against a live proxy server after cleanup.

#### Scenario: Chat completions integration smoke
- **WHEN** a smoke test sends a real request to a running proxy at `/v1/chat/completions`
- **THEN** the response is 200 or a well-formed error (not a 500 from missing imports)

#### Scenario: Messages endpoint integration smoke
- **WHEN** a smoke test sends a real request to a running proxy at `/v1/messages`
- **THEN** the response is 200 or a well-formed error (not a 500 from missing imports)

#### Scenario: Models endpoint integration smoke
- **WHEN** a smoke test sends GET to a running proxy at `/v1/models`
- **THEN** the response is 200 with a valid model list

