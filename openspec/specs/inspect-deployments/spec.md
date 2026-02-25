# inspect-deployments Specification

## Purpose
Provide a CLI command to inspect and list deployments with backend model names for all configured subaccounts.

## Requirements

### Requirement: Structured Logging in inspect_deployments

The `inspect_deployments.py` script SHALL use the logger for all user-facing output instead of `print()` statements, maintaining consistency with the project's logging approach.

#### Scenario: Normal operation output

- **WHEN** `inspect_deployments.py` runs successfully
- **THEN** all output SHALL be routed through `logger.info()` instead of `print()`
- **AND** the output format and content SHALL remain visually identical to users

#### Scenario: Subaccount inspection starts

- **WHEN** the script begins inspecting a subaccount
- **THEN** a log message SHALL indicate which subaccount is being processed
- **AND** the message SHALL be at INFO level for visibility

#### Scenario: No deployments found

- **WHEN** a subaccount has no deployments
- **THEN** the system SHALL log "No deployments found" at INFO level
- **AND** processing SHALL continue to the next subaccount

#### Scenario: Error during inspection

- **WHEN** an exception occurs during subaccount inspection
- **THEN** it SHALL be logged at ERROR level with full context
- **AND** processing SHALL continue gracefully

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

