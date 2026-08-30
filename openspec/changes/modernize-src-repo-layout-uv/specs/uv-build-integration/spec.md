## Purpose

Defines modern PEP 621 / PEP 517 packaging standards using `hatchling` as the build backend and consolidates tool configurations within `pyproject.toml`.

## ADDED Requirements

### Requirement: Modern Hatchling build system
The project packaging SHALL use `hatchling` as its PEP 517 build backend in `pyproject.toml` with zero-boilerplate automatic package discovery from `src/`.

#### Scenario: Building distribution artifacts
- **WHEN** `uv build` or `python -m build` is executed
- **THEN** valid wheel and sdist packages containing `saip` are produced without requiring manual package lists.

### Requirement: CLI entry point configuration
The project configuration SHALL expose the executable CLI scripts mapped to the new package structure.

#### Scenario: Running CLI proxy entry point
- **WHEN** running `sap-ai-proxy` command via `uv run` or installed binary
- **THEN** it executes `saip.main:main` cleanly.

### Requirement: Single configuration source of truth
The project SHALL consolidate testing, linting, type checking, and coverage configuration inside `pyproject.toml`, removing standalone legacy configuration files like `pytest.ini`.

#### Scenario: Running tests and coverage without pytest.ini
- **WHEN** `pytest` or `uv run pytest` is executed
- **THEN** pytest discovers configuration options, markers, and coverage settings directly from `[tool.pytest.ini_options]` and `[tool.coverage]` in `pyproject.toml`.
