## Context

The current repository layout has evolved from a single script to a modular FastAPI service, but retains a flat root structure where application modules (`auth/`, `config/`, `handlers/`, `routers/`, `utils/`, `main.py`, `proxy_helpers.py`, etc.) sit directly in the repository root. See `proposal.md` for motivation.

## Goals / Non-Goals

**Goals:**
- Move all core package code into `src/saip/`.
- Switch build backend in `pyproject.toml` to `hatchling`.
- Move diagnostic and operational scripts to `scripts/`.
- Reorganize orphaned test files in `tests/` into `tests/unit/` and ensure all 770+ tests pass with `saip` imports.
- Consolidate test and coverage settings into `pyproject.toml` and remove `pytest.ini`.
- Modernize `Makefile` with clean `uv`-native targets without redundant syncing.

**Non-Goals:**
- Modifying proxy business logic, converter logic, or API routing contracts.
- Changing runtime dependencies or minimum supported Python version (Python 3.13).

## Decisions

### 1. Package Namespace: `saip`
- **Choice**: Package code is structured under `src/saip/`.
- **Rationale**: `saip` is concise, clear, and avoids verbose naming while preventing root namespace collisions.
- **Alternatives Considered**: `sap_ai_core_llm_proxy` (verbose, longer imports).

### 2. Build Backend: `hatchling`
- **Choice**: Use `hatchling` as the build backend in `pyproject.toml`:
  ```toml
  [build-system]
  requires = ["hatchling"]
  build-backend = "hatchling.build"
  ```
- **Rationale**: `hatchling` is the default modern standard recommended by Astral for `uv`. It auto-discovers `src/saip` with zero manual package list maintenance.
- **Alternatives Considered**: `setuptools` with `[tool.setuptools.packages.find]` (functional, but legacy compared to modern Hatchling standard).

### 3. Source Directory Structure
- The directory tree will be:
  ```
  src/
  └── saip/
      ├── __init__.py
      ├── __main__.py
      ├── cli.py
      ├── main.py
      ├── load_balancer.py
      ├── proxy_helpers.py
      ├── version.py
      ├── proxy_server.py
      ├── auth/
      ├── config/
      ├── handlers/
      ├── routers/
      └── utils/
  ```

### 4. Scripts Directory Structure
- Non-package scripts move to `scripts/`:
  - `inspect_deployments.py`
  - `load_testing.py`
  - `test_mmyydd_logging.py`
  - `test_yyyymmdd_logging.py`

### 5. Test Organization & pyproject.toml Consolidation
- Reorganize test files into `tests/unit/`, `tests/integration/`, `tests/api/`.
- Migrate all `pytest.ini` options into `[tool.pytest.ini_options]`, `[tool.coverage.run]`, and `[tool.coverage.report]` in `pyproject.toml`.
- Update test imports: replace `from auth import ...` with `from saip.auth import ...`.

### 6. Makefile Modernization
- Remove repetitive `$(UV) sync --group dev &&` from test commands. `uv run` handles environment checks automatically.
- Provide clean lifecycle targets: `sync`, `check`, `lint`, `format`, `typecheck`, `test`, `test-unit`, `test-integration`, `test-cov`, `build-wheel`, `build-bin`, `clean`.

## Risks / Trade-offs

- **[Risk: Broken imports in tests]** → **Mitigation**: Update imports across all test files systematically and run `uv run pytest` to verify 100% test pass rate.
- **[Risk: Broken PyInstaller binary builds]** → **Mitigation**: Update `Makefile` and `proxy.spec` entry point references to `src/saip/main.py`.
- **[Risk: Backward compatibility during transition]** → **Mitigation**: `src/saip/proxy_server.py` and `__main__.py` will provide seamless entry points for legacy invocations.
