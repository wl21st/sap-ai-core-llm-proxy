## 1. Configuration Schema Updates

- [ ] 1.1 Add `ModelFilters` dataclass to `config/config_models.py` with `include: Optional[List[str]]` and `exclude: Optional[List[str]]` fields
- [ ] 1.2 Add `model_filters: Optional[ModelFilters]` field to `ProxyConfig` dataclass in `config/config_models.py`
- [ ] 1.3 Add Pydantic validation to ensure `include` and `exclude` are lists of strings if provided

## 2. Regex Pattern Validation

- [ ] 2.1 Create helper function `validate_regex_patterns(patterns: List[str], filter_type: str) -> List[re.Pattern]` in `config/config_parser.py` that compiles and validates regex patterns
- [ ] 2.2 Add error handling in validation function to catch `re.error` exceptions and raise clear `ConfigValidationError` with pattern and error details
- [ ] 2.3 Call validation function during config parsing for both include and exclude patterns

## 3. Model Filtering Logic

- [ ] 3.1 Create `apply_model_filters(models: Dict[str, List[str]], filters: ModelFilters) -> Tuple[Dict[str, List[str]], List[str]]` function in `config/config_parser.py` that returns filtered models and list of filtered model names
- [ ] 3.2 Implement filter precedence logic: if exclude patterns exist and model matches any, filter out; elif include patterns exist and model does NOT match any, filter out; else keep model
- [ ] 3.3 Track which models are filtered and by which pattern (for logging)
- [ ] 3.4 Return both filtered model dict and list of filtered model names with reasons

## 4. Integration with Config Parser

- [ ] 4.1 Update `parse_config()` function in `config/config_parser.py` to parse `model_filters` section if present
- [ ] 4.2 Apply model filters to each subaccount's `deployment_models` dict after parsing but before creating `SubAccountConfig` objects
- [ ] 4.3 Update `SubAccountConfig.model_to_deployment_urls` to only contain models that passed filtering
- [ ] 4.4 Ensure global `model_to_subaccounts` mapping only includes filtered models

## 5. Filter Logging

- [ ] 5.1 Add INFO-level log message at startup showing filter configuration (number of include/exclude patterns)
- [ ] 5.2 For each subaccount, log model counts before and after filtering with filtered model names
- [ ] 5.3 Add DEBUG-level logging showing which specific pattern matched each filtered model
- [ ] 5.4 Add WARNING-level log if all models in a subaccount are filtered out (zero models remaining)

## 6. Backwards Compatibility Testing

- [ ] 6.1 Verify that config files without `model_filters` section work unchanged (all models loaded)
- [ ] 6.2 Verify that empty `model_filters: {}` works unchanged
- [ ] 6.3 Verify that `model_filters` with empty arrays (`include: []`, `exclude: []`) works unchanged

## 7. Unit Tests for Model Filtering

- [ ] 7.1 Add test for valid regex pattern compilation in `tests/test_config_parser.py`
- [ ] 7.2 Add test for invalid regex pattern rejection with clear error message
- [ ] 7.3 Add test for include-only filtering (keeps matching models, filters out non-matching)
- [ ] 7.4 Add test for exclude-only filtering (filters out matching models, keeps non-matching)
- [ ] 7.5 Add test for combined include+exclude filtering (include first, then exclude from included set)
- [ ] 7.6 Add test verifying filter precedence matches spec (exclude after include)
- [ ] 7.7 Add test for empty/missing `model_filters` (no filtering applied)
- [ ] 7.8 Add test for all models filtered out in a subaccount (warning logged, zero models)

## 8. Integration Testing

- [ ] 8.1 Create test config file with `model_filters` that excludes test models
- [ ] 8.2 Verify `/v1/models` endpoint does not return filtered models
- [ ] 8.3 Verify requests to filtered models return 404 Not Found with "not_found_error" type
- [ ] 8.4 Verify requests to non-filtered models work normally
- [ ] 8.5 Test include filter only scenario (only GPT models exposed)
- [ ] 8.6 Test exclude filter only scenario (test models hidden)
- [ ] 8.7 Test combined include+exclude scenario (GPT models except preview variants)

## 9. Documentation Updates

- [ ] 9.1 Add `model_filters` example to `config.json.example` or sample configs
- [ ] 9.2 Update `CLAUDE.md` with model filtering feature description and config example
- [ ] 9.3 Update `README.md` if it contains configuration documentation
- [ ] 9.4 Add inline code comments explaining filter precedence logic

## 10. Error Handling and Edge Cases

- [ ] 10.1 Handle case where regex pattern is valid but matches no models (log info, not error)
- [ ] 10.2 Ensure filtered models don't appear in load balancer rotation
- [ ] 10.3 Verify model normalization happens before filtering (or vice versa, document decision)
- [ ] 10.4 Test behavior when include patterns match nothing (all models filtered out)
