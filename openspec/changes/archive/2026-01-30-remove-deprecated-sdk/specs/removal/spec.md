# Removal of Deprecated SDKs

## REMOVED Requirements

### Requirement: AI Core Legacy SDKs
The deprecated `ai-api-client-sdk` and `ai-core-sdk` libraries are no longer needed and shall be removed.

#### Scenario: Clean `pyproject.toml`
- **Given** the `pyproject.toml` file contains `ai-api-client-sdk` and `ai-core-sdk`
- **When** the cleanup is applied
- **Then** `ai-api-client-sdk` and `ai-core-sdk` should be removed from the `dependencies` list
