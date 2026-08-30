## 1. Source Layout Migration

- [ ] 1.1 Create `src/sap_ai_proxy/` directory structure and relocate `auth/`, `config/`, `handlers/`, `routers/`, `utils/`, `main.py`, `cli.py`, `version.py`, `load_balancer.py`, `proxy_helpers.py`, and `proxy_server.py` into it.
- [ ] 1.2 Create `src/sap_ai_proxy/__init__.py` and `src/sap_ai_proxy/__main__.py` to provide package metadata and executable module entry point.
- [ ] 1.3 Update internal import statements across all files under `src/sap_ai_proxy/` to use `sap_ai_proxy.*` (or package-relative imports).

## 2. Scripts Reorganization

- [ ] 2.1 Create top-level `scripts/` directory and move standalone scripts (`inspect_deployments.py`, `load_testing.py`, `test_mmyydd_logging.py`, `test_yyyymmdd_logging.py`) into `scripts/`.
- [ ] 2.2 Update import statements in `scripts/` to import from `sap_ai_proxy`.

## 3. Build System & Configuration Modernization

- [ ] 3.1 Update `pyproject.toml` to switch the build backend from setuptools to `hatchling.build` and configure entry points to `sap_ai_proxy.main:main`.
- [ ] 3.2 Consolidate test configuration from `pytest.ini` into `[tool.pytest.ini_options]` and `[tool.coverage.*]` inside `pyproject.toml`, then remove `pytest.ini`.
- [ ] 3.3 Run `uv sync` to install `sap_ai_proxy` in editable mode and verify package resolution.

## 4. Test Suite Reorganization & Verification

- [ ] 4.1 Move orphaned test files from `tests/` root (`test_proxy_server.py`, `test_proxy_helpers.py`, `test_conservative_retry.py`, `test_config_parser.py`, `test_helpers.py`, `test_proxy_server_extended.py`) into `tests/unit/`.
- [ ] 4.2 Update test imports across all test modules in `tests/` to reference `sap_ai_proxy.*`.
- [ ] 4.3 Run `uv run pytest` and verify all 770+ unit, integration, and API tests pass.

## 5. Makefile Modernization & Quality Gates

- [ ] 5.1 Refactor `Makefile` to remove redundant `uv sync` invocations from test targets and update script paths to `src/sap_ai_proxy/main.py`.
- [ ] 5.2 Add standardized lifecycle targets to `Makefile` (`make check`, `make lint`, `make typecheck`, `make test-unit`, `make build-wheel`).
- [ ] 5.3 Execute `make check` and `make build-wheel` to verify end-to-end linting, typing, testing, and wheel generation.
