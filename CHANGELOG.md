# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.7] - 2025-12-30

### Fixed
- **Critical Streaming Bug**: Fixed stream_id initialization and token counter bugs in Claude 3.7/4 streaming (`proxy_helpers.py`, `proxy_server.py`)
  - Initialize `stream_id` with fallback value before streaming loop to prevent race condition
  - Initialize token counters (`total_tokens`, `prompt_tokens`, `completion_tokens`) before loop to prevent NameError
  - Improved messageStart ID extraction to replace fallback instead of conditional initialization
  - Expanded random ID ranges from 5 to 8 digits for better collision avoidance
  - Fixes potential bugs where:
    1. messageStart chunk could be skipped if converted before ID extraction
    2. Token variables could cause NameError if metadata chunk never arrives
    3. Final usage chunk could have null id if messageStart never arrives
- **Token Usage Regression**: Fixed token usage regression introduced in v1.2.5 affecting Sonnet 4.5 streaming responses

### Documentation
- **Architecture Review**: Added comprehensive architecture review and improvement plan (`docs/plans/architecture_review_and_improvement_plan.md` - 861 lines)
- **Bug Reports**: Added detailed bug report and fix documentation for Sonnet 4.5 token usage issue:
  - `docs/BUG_REPORT_sonnet-4.5-token-usage-regression.md` (243 lines)
  - `docs/FIX_sonnet-4.5-regression.md` (94 lines)
  - `docs/sonnet-4.5-token-usage-issue.md` (160 lines)
- **Agent Guidelines**: Updated `AGENTS.md` with comprehensive architecture overview:
  - Corrected test count (50+ tests, 28% coverage)
  - Added Architecture Overview with request flow diagram
  - Expanded Code Style section with detailed PEP 8 naming conventions
  - Added Critical Implementation Details (token management, load balancing, model detection, retry logic)
  - Added Known Technical Debt section
- **Code Documentation**: Updated `CLAUDE.md` with current line counts (proxy_server.py: 2501, proxy_helpers.py: 1414)

### Changed
- **Test Improvements**: Fixed logging utils tests with correct archive directory name ('archives') and patching strategy
- **Code Quality**: Added clarifying comment for model detection normalization (dots to hyphens)

### Technical Details
- **Lines Changed**: 1,661 insertions, 67 deletions (net addition of 1,594 lines, primarily documentation)
- **Files Modified**: 15 files across proxy core, documentation, and tests
- **Bug Fixes**: 2 critical streaming and token usage bugs resolved
- **Documentation**: Significant expansion of architecture and troubleshooting documentation

## [1.2.6] - 2025-12-29

### Added
- **ProxyGlobalContext**: Introduced singleton global context (similar to Spring Boot's ApplicationContext) for centralized configuration and service management
- **SSE Implementation Analysis**: Added comprehensive documentation analyzing SSE payload conversion compliance (`docs/SSE_Implementation_Analysis.md`)
- **Enhanced Testing**: Improved test coverage for non-Claude model fallback scenarios with better mocking

### Changed
- **Architecture Refactoring**: Major refactoring of configuration management:
  - Introduced `ProxyGlobalContext` in `config/global_context.py` for thread-safe singleton service management
  - Refactored `config_parser.py` with enhanced configuration loading (82+ new lines)
  - Simplified `config_models.py` by removing 70+ lines of redundant code
  - Updated proxy server to use centralized context for token managers and services
- **Code Quality**: Cleaned up unused imports across 8+ files including tests and utilities
- **Type Annotations**: Fixed type annotations in proxy server for better type safety
- **Test Improvements**: Updated 87+ lines in test files to match new architecture patterns

### Removed
- **Pydantic Configuration System**: Removed unused Pydantic-based configuration system (~1,016 lines):
  - Deleted `config/pydantic_loader.py` (190 lines)
  - Deleted `config/pydantic_models.py` (121 lines)
  - Deleted `config/README_PYDANTIC.md` (247 lines)
  - Deleted `test_pydantic_config.py` (248 lines)
  - Deleted `PYDANTIC_CONFIG_SUMMARY.md` (206 lines)
- **Dead Code**: Removed unused imports and simplified proxy helper methods (18 lines reduced)

### Fixed
- Improved token manager initialization through global context for better thread safety
- Fixed type annotations in streaming SSE conversion functions

### Documentation
- Updated `docs/Backlog.md` to reflect completed refactoring tasks
- Added detailed SSE implementation analysis documenting compliance gaps and improvement areas

### Technical Details
- **Lines Changed**: 447 insertions, 1,189 deletions (net reduction of 742 lines)
- **Files Modified**: 24 files across config, tests, and core modules
- **Architecture**: Moved toward centralized service management pattern with ProxyGlobalContext
- **Thread Safety**: Enhanced thread-safe access to token managers via singleton context with locks

## [1.2.3] - 2025-12-25

### Fixed
- Fixed global proxy configuration initialization in main() entry point to ensure proper configuration loading when running via uvx

### Changed
- Minor bug fix release to address configuration loading issue introduced in v1.2.2

## [1.2.2] - 2025-12-25

### Added
- **UVX Support**: Added main() entry point function for better modularity and uvx compatibility
- **Entry Point Configuration**: Configured `project.scripts` in pyproject.toml to enable `sap-ai-proxy` command
- **Comprehensive Documentation**:
  - Added `docs/UVX_USAGE.md` - Complete guide for running with uvx (now recommended method)
  - Added `docs/CHANGELOG_UVX.md` - Detailed documentation of the uvx migration
  - Added `CLAUDE.md` - Comprehensive project documentation (345 lines) covering architecture, development commands, testing, and conventions
- **Transport Logging**: Added HTTP request/response tracing with UUID trace IDs for better debugging
- **Modern Type Hints**: Migrated from legacy typing imports (Dict, List, Optional) to modern Python 3.10+ syntax (dict, list, | None)
- **Enhanced Configuration**: Added `api_url` field to ServiceKey dataclass and `get_subaccount()` helper method to ProxyConfig

### Changed
- **Recommended Installation Method**: uvx is now the recommended way to run the proxy:
  - `uvx --from . sap-ai-proxy --config config.json` (local)
  - `uvx sap-ai-proxy --config config.json` (after PyPI publishing)
- **Improved Logging**: Enhanced log formatter to include filename and line number for better traceability
- **SDK Integration**: Improved SDK client initialization by passing subaccount config explicitly
- **Code Quality**: Simplified error handling and improved code formatting across modules
- **Test Updates**: Updated tests to match new type signatures

### Development
- **Setuptools Configuration**: Added setuptools configuration for proper package structure
- **README Updates**: Updated README.md with uvx usage instructions and examples
- **CLAUDE.md Updates**: Updated with uvx examples and references to new documentation
- **HTTP Logging Utilities**: Added `utils/http_logging.py` with 92 lines of transport logging utilities
- **Dependencies**:
  - Added `uuid` dependency for generating trace IDs
  - Moved `black` formatter to dev dependencies

### Refactoring
- Removed unused imports and cleaned up code formatting
- Improved SDK pool documentation
- Updated config naming conventions across documentation

## [1.2.1] - (Previous Release)

### Notes
- See git history for changes prior to v1.2.2

---

## Version Comparison

**v1.2.7 vs v1.2.6**: Critical bug fix release for Claude 3.7/4 streaming issues (stream_id, token counters) and v1.2.5 token usage regression, with extensive architecture documentation
**v1.2.6 vs v1.2.5**: Major refactoring release with ProxyGlobalContext, removed Pydantic config system (net -742 lines), enhanced architecture
**v1.2.3 vs v1.2.2**: Bug fix for global configuration loading issue
**v1.2.2 vs v1.2.1**: Major feature release with uvx support, comprehensive documentation, transport logging, and modern type hints

## Migration Guide

### Upgrading to v1.2.2+

The recommended way to run the proxy has changed to use uvx:

**Before (v1.2.1 and earlier):**
```bash
python proxy_server.py --config config.json
```

**After (v1.2.2+):**
```bash
# Local development
uvx --from . sap-ai-proxy --config config.json

# After PyPI publishing
uvx sap-ai-proxy --config config.json
```

The traditional Python execution method is still supported, but uvx is now recommended for:
- No installation required
- Automatic dependency management
- Isolated environments
- Simplified deployment

See `docs/UVX_USAGE.md` for complete migration guide and usage examples.
