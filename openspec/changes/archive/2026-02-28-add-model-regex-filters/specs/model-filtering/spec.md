# Spec: Model Filtering

## Purpose
Configuration-based filtering of model IDs using inclusive/exclusive regex patterns applied during config parsing to control which models are exposed through the API.

## ADDED Requirements

### Requirement: Model Filter Configuration
The system SHALL support an optional `model_filters` configuration section in `config.json` with `include` and `exclude` fields, each accepting a list of regex pattern strings.

#### Scenario: Config with include filters
- **WHEN** config.json contains `"model_filters": {"include": ["^gpt-.*", "^claude-4.*"]}`
- **THEN** system SHALL only load models matching at least one include pattern
- **AND** system SHALL filter out all other models during config parsing

#### Scenario: Config with exclude filters
- **WHEN** config.json contains `"model_filters": {"exclude": [".*-test$", "^gemini-1.*"]}`
- **THEN** system SHALL filter out models matching any exclude pattern
- **AND** system SHALL load all other configured models

#### Scenario: Config with both include and exclude filters
- **WHEN** config.json contains both include and exclude pattern lists
- **THEN** system SHALL first apply include filters (if present) to keep only matching models
- **AND** system SHALL then apply exclude filters to remove matching models from the included set

#### Scenario: Config without model_filters
- **WHEN** config.json does not contain a `model_filters` section
- **THEN** system SHALL load all configured models without filtering
- **AND** behavior SHALL be identical to current implementation

### Requirement: Regex Pattern Validation
The system SHALL validate all regex patterns in `model_filters` during config loading and SHALL reject invalid patterns with a clear error message.

#### Scenario: Valid regex patterns
- **WHEN** config contains valid regex patterns like `"^gpt-4.*"` or `"claude-(opus|sonnet)-.*"`
- **THEN** system SHALL accept the patterns and apply them during filtering
- **AND** config loading SHALL succeed

#### Scenario: Invalid regex patterns
- **WHEN** config contains an invalid regex pattern like `"[unclosed"` or `"(?P<invalid"`
- **THEN** system SHALL raise a configuration error during startup
- **AND** error message SHALL identify the invalid pattern and the regex compilation error

### Requirement: Model Filtering Application
The system SHALL apply model filters during config parsing before building the internal model registry, ensuring filtered-out models are never registered.

#### Scenario: Model excluded by filter
- **WHEN** config has `deployment_models: {"gpt-4-test": ["url1"], "gpt-4": ["url2"]}` and `model_filters: {"exclude": [".*-test$"]}`
- **THEN** system SHALL not register "gpt-4-test" in any internal data structures
- **AND** system SHALL register "gpt-4" normally
- **AND** "gpt-4-test" SHALL behave as if it was never configured

#### Scenario: All subaccount models filtered out
- **WHEN** all models in a subaccount's deployment_models are filtered out by patterns
- **THEN** system SHALL treat that subaccount as having zero available models
- **AND** system SHALL not select that subaccount during load balancing

### Requirement: Filter Logging
The system SHALL log model filtering results at startup to provide visibility into which models were filtered and why.

#### Scenario: Models filtered at startup
- **WHEN** system applies filters during config loading
- **THEN** system SHALL log each filtered model with the pattern that excluded it
- **AND** log level SHALL be INFO or DEBUG
- **AND** log format SHALL include: filtered model name, filter type (include/exclude), matching pattern

#### Scenario: No models filtered
- **WHEN** filters are configured but no models match filter criteria
- **THEN** system SHALL log that filters were applied but no models were affected
- **AND** system SHALL proceed normally with all configured models

### Requirement: Filter Precedence
The system SHALL apply include filters before exclude filters when both are specified, with exclude filters acting as exceptions to the include list.

#### Scenario: Include filter with exclude exceptions
- **WHEN** config has `"include": ["^gpt-.*"]` and `"exclude": [".*-preview$"]`
- **AND** deployment_models contains "gpt-4", "gpt-4-preview", "claude-sonnet"
- **THEN** system SHALL first filter to only models matching `^gpt-.*` (keeps "gpt-4" and "gpt-4-preview", removes "claude-sonnet")
- **AND** system SHALL then remove models matching `.*-preview$` (removes "gpt-4-preview")
- **AND** final result SHALL contain only "gpt-4"
