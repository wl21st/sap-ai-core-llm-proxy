## 1. Config Model Updates

- [ ] 1.1 Add `auto_discover: bool = False` field to `SubAccountConfig` dataclass in `config/config_models.py`
- [ ] 1.2 Add `auto_discover` field to the corresponding Pydantic schema in `config/config_parser.py` and wire it through to the dataclass
- [ ] 1.3 Add unit tests for config parsing with `auto_discover: true` and without (backward compat)

## 2. SDK Utility: Orchestration Model Name Extraction

- [ ] 2.1 Extend model-name extraction in `fetch_all_deployments()` (`utils/sdk_utils.py`) to fall back to `configuration_name` when `backend_details.model.name` is absent
- [ ] 2.2 Ensure deployments with no `model_name` and no `configuration_name` still appear in results with `model_name: None`
- [ ] 2.3 Add/update unit tests in `tests/unit/test_sdk_utils.py` covering: orchestration deployment (config name used), model-serving deployment (backend name used), neither present (None result)

## 3. Discovery Module

- [ ] 3.1 Create `discovery.py` at project root with a `run_discovery(config: ProxyConfig) -> None` function
- [ ] 3.2 Implement eligibility check: run discovery when `auto_discover=True` OR when both `deployment_models` and `model_to_deployment_ids` are empty
- [ ] 3.3 Implement merge logic: for each discovered deployment with non-None `model_name`, append URL to `model_to_deployment_urls[model_name]` if not already present; manual URLs preserved
- [ ] 3.4 Apply alias expansion for newly discovered model names using `MODEL_ALIASES` from `proxy_helpers.py`
- [ ] 3.5 Wrap per-subaccount discovery in try/except; log WARNING on failure and continue
- [ ] 3.6 Log DEBUG for skipped deployments (None model_name); log INFO for each model registered
- [ ] 3.7 Add unit tests in `tests/unit/test_discovery.py` covering: merge with existing manual config, new model from discovery, failure tolerance, alias expansion, skip None model_name

## 4. Startup Integration

- [ ] 4.1 Call `run_discovery(config)` inside `lifespan()` in `main.py` after `load_proxy_config()` and before `context.initialize(config)`
- [ ] 4.2 Verify that `model_to_subaccounts` in `ProxyGlobalContext.initialize()` correctly picks up the newly merged URLs (no changes expected, but confirm)
- [ ] 4.3 Add integration-level test or update existing conftest to verify that a subaccount with `auto_discover: true` and no `deployment_models` results in models being available after startup (can be a mocked test)

## 5. Documentation & Validation

- [ ] 5.1 Update `CLAUDE.md` config example to show `auto_discover: true` usage
- [ ] 5.2 Run `make test` to confirm all 50+ unit tests pass
- [ ] 5.3 Run `uv run basedpyright` to confirm no type errors in new/modified files
- [ ] 5.4 Manual smoke test: start proxy with `auto_discover: true` subaccount pointing at a real SAP AI Core instance; verify orchestration deployment appears in `/v1/models` response
