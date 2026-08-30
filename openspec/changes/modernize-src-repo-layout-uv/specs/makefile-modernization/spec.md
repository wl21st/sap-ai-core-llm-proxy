## Purpose

Provides a streamlined, lifecycle-oriented Makefile leveraging `uv` commands directly without redundant environment synchronizations.

## ADDED Requirements

### Requirement: Idiomatic UV Make targets
The `Makefile` SHALL define fast, non-redundant targets utilizing `uv run` for quality checks, tests, builds, and local development.

#### Scenario: Running quick quality checks
- **WHEN** developer runs `make check`
- **THEN** linting (`ruff`), type checking (`pyright`), and unit tests execute in sequence via `uv run`.

#### Scenario: Building release packages
- **WHEN** developer runs `make build-wheel`
- **THEN** package wheels are built using `uv build` without manual pre-sync steps.
