## Purpose

Provides a clean, collision-free source package structure under `src/saip/` ensuring isolated distribution namespaces and accurate package imports.

## ADDED Requirements

### Requirement: Application code lives in isolated `src/saip` package
The repository SHALL organize all application source code, modules, and subpackages under `src/saip/`.

#### Scenario: Importing modules from the package
- **WHEN** importing application components in code or tests
- **THEN** imports resolve via the `saip` package namespace (e.g. `from saip.config import ProxyConfig`)

#### Scenario: Prevent namespace pollution in site-packages
- **WHEN** building or installing the package in an environment
- **THEN** only the `saip` namespace package is registered in `site-packages`, with no generic top-level packages (`auth`, `config`, `utils`, `handlers`, `routers`).

### Requirement: Standalone utility and diagnostic scripts are isolated
The repository SHALL place diagnostic, maintenance, and standalone utility scripts in a top-level `scripts/` directory outside of the package namespace.

#### Scenario: Running diagnostic and helper scripts
- **WHEN** running scripts such as `inspect_deployments.py` or load testing tools
- **THEN** they execute from the `scripts/` directory and import dependencies from `saip`.
