## ADDED Requirements

### Requirement: Inspect Deployments CLI
The system SHALL provide a CLI command to inspect and list deployments for configured subaccounts.

#### Scenario: List deployments
- **WHEN** the user runs the inspection command (e.g., `python proxy_server.py --inspect`)
- **THEN** the system iterates through all configured subaccounts
- **AND** fetches all deployments
- **AND** prints a table showing Deployment ID, Deployment URL, and Backend Model Name

#### Scenario: Help output
- **WHEN** the user runs the inspection command
- **THEN** the output format is human-readable (e.g., aligned columns) to assist with `config.json` creation
