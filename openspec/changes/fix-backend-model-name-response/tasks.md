## 1. SDK Utilities Updates

- [x] 1.1 Update `utils/sdk_utils.py` to add `fetch_all_deployments` (Done).
- [ ] 1.2 Implement the extraction logic for `backend_details.model.name` (Done/Refining).
- [ ] 1.3 Add unit tests (In Progress).

## 2. Caching & Config Enhancements (NEW)

- [ ] 2.1 Update `utils/sdk_utils.py` to use `diskcache`.
    - Decorate or wrap `fetch_all_deployments`.
    - Configure cache path (`.cache/deployments`) and expiry (7 days).
- [ ] 2.2 Update `proxy_helpers.py` to load `MODEL_ALIASES` from `config/aliases.json`.
- [ ] 2.3 Create default `config/aliases.json` (Done).
- [ ] 2.4 Update `.gitignore` to exclude `.cache/`.

## 3. Config & Initialization Logic

- [ ] 3.1 Modify `config/config_parser.py` (Done/Refining) to use the new aliasing logic.
- [ ] 3.2 Ensure backward compatibility.

## 4. CLI Updates

- [ ] 4.1 Implement `inspect_deployments.py` (Done).
- [ ] 4.2 Verify the CLI works.

## 5. Verification

- [ ] 5.1 Integration test: Start proxy with minimal config (no model mappings), mock SDK response, verify routing works for `sonnet-3.5`.
