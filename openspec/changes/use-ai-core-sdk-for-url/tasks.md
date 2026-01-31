# Tasks: Use SAP AI Core SDK for Deployment URL

- [ ] Update `SubAccountConfig` and `config_parser` to support `deployment_ids` in configuration
  - Allow users to configure `model_to_deployment_ids` directly in `config.json`
- [ ] Implement `fetch_deployment_url` using SAP AI Core SDK
  - Research correct SDK method (e.g., `ai_core_sdk.deployment.Deployment.get`)
  - Add function to `utils/sdk_utils.py` to resolve ID to URL
- [ ] Integrate URL fetching into `load_balance_url` or config loading phase
  - Modify `_build_mapping_for_subaccount` to fetch URLs for configured IDs
  - Populate `model_to_deployment_urls` dynamically
- [ ] Verify `proxy_server.py` works with SDK-resolved URLs
  - Ensure `endpoint_url` construction is correct
- [ ] Update documentation to reflect simplified configuration
