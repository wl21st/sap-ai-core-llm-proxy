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

