## Why

The current repository layout uses a flat, root-level module structure where generic directories (`auth/`, `config/`, `handlers/`, `routers/`, `utils/`) and loose `.py` modules are directly defined at the root and manually listed in `pyproject.toml`. This creates significant risks of namespace collisions in `site-packages`, allows test suites to import local files rather than the installed distribution package, splinters configuration between `pytest.ini` and `pyproject.toml`, leaves loose test files and scripts in root directories, and introduces overhead in `Makefile` with redundant `uv sync` calls.

Migrating to the standard Python `src/` layout with `sap_ai_proxy` as the top-level package, switching the build backend to `hatchling` (Astral's recommended backend for `uv`), reorganizing scripts and tests into standard directories, and modernizing the Makefile creates a robust, industry-standard packaging architecture.

## What Changes

- **Adopt `src/` Layout (`src/sap_ai_proxy/`)**: Relocate internal packages (`auth`, `config`, `handlers`, `routers`, `utils`) and core modules (`main`, `cli`, `load_balancer`, `proxy_helpers`, `version`, `proxy_server`) under `src/sap_ai_proxy/`.
- **Adopt `hatchling` Build Backend**: Replace `setuptools.build_meta` with `hatchling.build` in `pyproject.toml` with zero-boilerplate automatic source package discovery.
- **Top-Level Package Namespace**: Establish `sap_ai_proxy` as the clean import namespace (e.g. `from sap_ai_proxy.config import ProxyConfig`, `from sap_ai_proxy.auth import RequestValidator`).
- **Relocate Standalone Scripts**: Move root diagnostic and maintenance scripts (`inspect_deployments.py`, `load_testing.py`, `test_mmyydd_logging.py`, `test_yyyymmdd_logging.py`) into a dedicated top-level `scripts/` directory.
- **Categorize Test Hierarchy**: Move loose test files from `tests/` root into their appropriate `tests/unit/`, `tests/integration/`, or `tests/api/` directories, and update test import paths.
- **Consolidate Tooling in `pyproject.toml`**: Migrate test and coverage configuration from `pytest.ini` into `[tool.pytest.ini_options]`, `[tool.coverage.run]`, and `[tool.coverage.report]` in `pyproject.toml`, retiring `pytest.ini`.
- **Streamline `Makefile`**: Modernize Make targets to leverage `uv run` natively without redundant `uv sync` invocations on every command, adding standardized targets (`make check`, `make lint`, `make typecheck`, `make test-unit`, `make build-wheel`).

## Capabilities

### New Capabilities
- `src-package-layout`: Defines the standard `src/sap_ai_proxy/` package structure and isolated namespace for all application modules.
- `uv-build-integration`: Defines the `hatchling` build system, PEP 621 metadata, entrypoints, and consolidated tool configurations in `pyproject.toml`.
- `test-suite-structure`: Defines the test categorization hierarchy (`unit`, `integration`, `api`), fixture organization, and coverage bounds.
- `makefile-modernization`: Defines the standard set of `uv`-native lifecycle Make targets.

### Modified Capabilities
<!-- No requirement changes to runtime inference proxy endpoints -->

## Impact

**Code affected:**
- `src/sap_ai_proxy/` - Created containing `auth/`, `config/`, `handlers/`, `routers/`, `utils/`, `main.py`, `cli.py`, `version.py`, `load_balancer.py`, `proxy_helpers.py`, `proxy_server.py`.
- `scripts/` - Created containing `inspect_deployments.py`, `load_testing.py`, `test_mmyydd_logging.py`, `test_yyyymmdd_logging.py`.
- `pyproject.toml` - Updated build-system (`hatchling`), script entrypoint (`sap-ai-proxy = "sap_ai_proxy.main:main"`), and tool configs.
- `pytest.ini` - Removed (merged into `pyproject.toml`).
- `tests/` - Internal test imports updated to `sap_ai_proxy.*`, loose test files moved to `tests/unit/`.
- `Makefile` - Streamlined and organized by lifecycle.

**APIs:** No external HTTP API changes. CLI commands (`sap-ai-proxy`) retain exact same CLI interface and behavior.

**Dependencies:** Build system uses `hatchling>=1.26.0`. Runtime dependencies unchanged.

**Risk:** Low-to-medium. Package layout and import paths change, requiring automated verification across all 770+ unit and integration tests.
