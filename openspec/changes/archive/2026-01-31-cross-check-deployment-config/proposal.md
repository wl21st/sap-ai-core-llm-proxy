## Why
The current system allows users to manually map model names to deployment IDs without validation. If a user incorrectly maps a model alias (e.g., `gpt-4`) to a deployment running a different model (e.g., `gemini-1.5-pro`), the proxy will attempt to route traffic incorrectly, leading to runtime errors or unexpected behavior. Validating this mapping against the actual deployment metadata ensures configuration integrity.

## What Changes
- Implement a validation step during subaccount configuration parsing (`_build_mapping_for_subaccount`).
- Cross-check configured `model_name` -> `deployment_id` mappings against the actual `model_name` returned by the SAP AI Core API for that deployment.
- Validate matching based on:
  - **Family**: e.g., "claude" vs "gemini" vs "gpt"
  - **Variant**: e.g., "sonnet" vs "haiku"
  - **Version**: e.g., "4" vs "4.5" (strict version checking)
- Log a warning if a mismatch is detected (non-blocking for now).

## Capabilities

### New Capabilities
- `config-validation`: Validates configuration against runtime environment data, specifically ensuring manual model mappings match deployed resources.

### Modified Capabilities
- `<none>`

## Impact
- **Codebase**: `config/config_parser.py` (validation logic), `utils/model_utils.py` (new helper for model string comparison maybe?).
- **Behavior**: Startup logs will now contain warnings for misconfigured deployments. No blocking behavior introduced yet.
