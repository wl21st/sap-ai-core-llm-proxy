## Why

Currently, when a requested model (and its fallbacks) cannot be found in any subaccount, the proxy returns a 400 Bad Request error. This is semantically incorrect as the resource (model) is missing, not the request being malformed. Returning 404 Not Found provides a clearer indication to clients that the model is unavailable.

## What Changes

- Modify `blueprints/messages.py` to catch `ValueError` during model load balancing and return a 404 status code instead of 400.
- Ensure the error response body follows the standard error format with type `not_found_error` (or similar).

## Capabilities

### New Capabilities
<!-- Capabilities being introduced. Replace <name> with kebab-case identifier (e.g., user-auth, data-export, api-rate-limiting). Each creates specs/<name>/spec.md -->
- `model-resolution`: Logic for resolving model names to available deployments, handling fallbacks, and managing error states when models are unavailable.

### Modified Capabilities
<!-- Existing capabilities whose REQUIREMENTS are changing (not just implementation).
     Only list here if spec-level behavior changes. Each needs a delta spec file.
     Use existing spec names from openspec/specs/. Leave empty if no requirement changes. -->

## Impact

- **API Behavior**: The `/v1/messages` endpoint will return HTTP 404 instead of 400 when a model is not found.
- **Clients**: Clients relying on 400 for "model not found" checks will need to update to handle 404.
