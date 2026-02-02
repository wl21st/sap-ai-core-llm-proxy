## ADDED Requirements

### Requirement: Extract Backend Model Name
The SDK utility `fetch_deployment_url` (or a new function) SHALL extract the `backend_details.model.name` from the SAP AI Core deployment response and make it available to the caller.

#### Scenario: Backend details present
- **WHEN** fetching a deployment that has `details.resources.backend_details.model.name` populated
- **THEN** the function returns an object or tuple containing the model name (e.g., "gpt-4") along with the URL

#### Scenario: Backend details missing
- **WHEN** fetching a deployment that lacks `backend_details`
- **THEN** the function handles the missing key gracefully (e.g., returns None or a default value for the model name) without crashing
