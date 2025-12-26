# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
