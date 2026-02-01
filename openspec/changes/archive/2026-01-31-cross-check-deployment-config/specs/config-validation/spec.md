# Spec: Configuration Validation

## Purpose
Ensure that the manual configuration of model-to-deployment mappings in `config.json` aligns with the actual deployments in SAP AI Core to prevent misrouting and runtime errors.

## ADDED Requirements

### Requirement: Startup Configuration Validation
The system SHALL validate all manual model-to-deployment mappings in `config.json` against the actual deployment metadata fetched from SAP AI Core during startup. This validation SHALL check for mismatches in model family, variant, and version.

#### Scenario: Valid Configuration
- **WHEN** `config.json` maps `gpt-4` to deployment `d123`
- **AND** deployment `d123` has backend model `gpt-4`
- **THEN** the system logs that the mapping is verified
- **AND** the system proceeds without warnings

#### Scenario: Invalid Model Family
- **WHEN** `config.json` maps `gpt-4` to deployment `d456`
- **AND** deployment `d456` has backend model `gemini-1.5-pro`
- **THEN** the system logs a WARNING: "Configuration mismatch: Model 'gpt-4' mapped to deployment 'd456' which is running 'gemini-1.5-pro' (family mismatch)"

#### Scenario: Invalid Model Variant
- **WHEN** `config.json` maps `claude-3-5-sonnet` to deployment `d789`
- **AND** deployment `d789` has backend model `claude-3-haiku`
- **THEN** the system logs a WARNING: "Configuration mismatch: Model 'claude-3-5-sonnet' mapped to deployment 'd789' which is running 'claude-3-haiku' (variant mismatch)"

#### Scenario: Invalid Model Version
- **WHEN** `config.json` maps `gpt-4` to deployment `d999`
- **AND** deployment `d999` has backend model `gpt-3.5-turbo`
- **THEN** the system logs a WARNING: "Configuration mismatch: Model 'gpt-4' mapped to deployment 'd999' which is running 'gpt-3.5-turbo' (version mismatch)"

#### Scenario: Deployment Not Found
- **WHEN** `config.json` maps `gpt-4` to deployment `d000`
- **AND** deployment `d000` is not found in the fetched deployments list
- **THEN** the system logs a WARNING: "Configuration warning: Deployment 'd000' mapped to model 'gpt-4' not found in subaccount"
