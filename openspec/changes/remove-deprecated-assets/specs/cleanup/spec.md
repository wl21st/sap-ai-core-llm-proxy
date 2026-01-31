# Cleanup Deprecated Assets

## REMOVED Requirements

### Requirement: Remove Outdated Docs
The project shall no longer contain outdated planning and analysis documents from previous phases.

#### Scenario: Remove Phase 3 and 4 Docs
- **Given** the project contains outdated Phase 3 and Phase 4 documentation
- **When** the cleanup is applied
- **Then** the following files should be removed:
  - `docs/PHASE3_IMPROVEMENTS.md`
  - `docs/PHASE3_TEST_ANALYSIS.md`
  - `docs/PHASE3_COMPLETION.md`
  - `docs/PHASE4_IMPLEMENTATION_PLAN.md`
  - `docs/PHASE4_SUMMARY.md`
  - `docs/PHASE4_COMPLETION.md`
  - `docs/REFACTORING_PHASE2.md`

#### Scenario: Remove Resolved Issue Docs
- **Given** the project contains documentation for resolved bugs
- **When** the cleanup is applied
- **Then** the following files should be removed:
  - `docs/BUG_REPORT_sonnet-4.5-token-usage-regression.md`
  - `docs/FIX_sonnet-4.5-regression.md`
  - `docs/sonnet-4.5-token-usage-issue.md`
  - `docs/plans/architecture_review_and_improvement_plan.md`

### Requirement: Remove Legacy Code
Archived and unmaintained code shall be removed from the repository.

#### Scenario: Remove Archived Proxy Server
- **Given** the file `archive/proxy_server_litellm.py` exists
- **When** the cleanup is applied
- **Then** the file `archive/proxy_server_litellm.py` should be deleted

## MODIFIED Requirements

### Requirement: Deprecate Legacy Entry Point
The legacy entry point `proxy_server.py` SHALL emit a warning to users upon execution.

#### Scenario: Warn on Legacy Usage
- **Given** the `proxy_server.py` file is executed
- **When** the application starts
- **Then** a warning should be logged stating that `proxy_server.py` is deprecated and recommending `sap-ai-proxy` (via `main.py`)
