## 1. Validation Logic Implementation

- [x] 1.1 Implement `Detector.validate_model_mapping` in `proxy_helpers.py` to handle model string normalization and comparison logic (Family, Variant, Version).
- [x] 1.2 Create unit tests in `tests/unit/test_model_validation.py` to verify matching logic against various edge cases (e.g., `gpt-4` vs `gpt-4-0613`, `claude-3-sonnet` vs `claude-3-haiku`).

## 2. Config Integration

- [x] 2.1 Modify `config/config_parser.py` in `_build_mapping_for_subaccount` to invoke validation logic.
- [x] 2.2 Implement iterating through manual mappings and cross-referencing with `discovered_deployments` (fetched via `fetch_all_deployments` or `fetch_deployment_url`).
- [x] 2.3 Add warning logging for detected mismatches.

## 3. Verification

- [x] 3.1 Run unit tests to ensure no regressions in config parsing.
- [x] 3.2 Verify integration by simulating a mismatch (using a test case or mock).
