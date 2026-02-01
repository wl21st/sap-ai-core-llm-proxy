## Context
The proxy currently accepts user-defined mappings in `config.json` that link a model alias (e.g., `gpt-4`) to a deployment ID. There is no verification that the deployment ID actually points to a model of that type. This leads to difficult-to-debug runtime errors if a user misconfigures the proxy (e.g., pointing `gpt-4` to a `gemini` deployment).

## Goals / Non-Goals

**Goals:**
- Detect mismatches between configured model names and actual backend models at startup.
- Log clear warnings identifying the specific mismatch (Family, Variant, or Version).
- Support standard model names and common aliases.

**Non-Goals:**
- blocking startup on mismatch (soft launch).
- Automatically correcting the configuration.
- validating parameters other than model name (e.g., version updates).

## Decisions

### 1. Validation Logic Location
We will implement the validation logic within `_build_mapping_for_subaccount` in `config/config_parser.py`.
**Rationale:** This function already iterates through configured deployments and has access to the `fetch_all_deployments` data (via auto-discovery logic), making it the most efficient place to cross-check without extra API calls.

### 2. Validation Helper
We will add a static method `validate_model_mapping(configured_name, backend_model_name)` to a new class or existing `Detector` in `proxy_helpers.py`.
**Rationale:** Centralizes model string parsing logic. `proxy_helpers.py` already contains `Detector` for model family detection, so it fits well there.

### 3. Matching Strategy
The matching logic will check for three levels of mismatch:
1.  **Family Mismatch:** Checks if both belong to same family (GPT, Claude, Gemini). If one is GPT and other is Gemini -> Mismatch.
2.  **Variant Mismatch:** Checks specific keywords like "sonnet", "haiku", "pro", "flash". If configured as "sonnet" but backend is "haiku" -> Mismatch.
3.  **Version Mismatch:** Checks major/minor version numbers. "4" vs "3.5".

**Normalization:** Both strings will be normalized (lowercase, `.` replaced with `-`).

### 4. Logging
Warnings will be logged using `logger.warning` with a structured message format:
`"Configuration mismatch: Model '{configured}' mapped to deployment '{id}' which is running '{backend}' ({reason})"`

## Risks / Trade-offs

**Risk:** False Positives due to alias differences (e.g., config `gpt-4`, backend `gpt-4-32k`).
**Mitigation:**
- We will rely on `Detector` logic which is generally substring based.
- We will prioritize "Family" mismatches which are the most critical.
- We will check if the configured name is a known alias of the backend model using `MODEL_ALIASES`.

**Risk:** Blocking valid deployments during an outage.
**Mitigation:** We explicitly chose NOT to block startup, only warn.
