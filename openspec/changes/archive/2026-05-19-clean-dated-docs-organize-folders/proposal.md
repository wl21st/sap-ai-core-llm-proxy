## Why

Outdated documentation in the repository leads to confusion for developers integrating with SAP AI Core LLM Proxy, resulting in incorrect implementations and increased support overhead. Additionally, the current folder structure is inconsistent and lacks clear naming conventions, making it difficult to locate relevant files and understand the project layout.

## What Changes

- **Documentation cleanup**: Archive the dated test report `docs/tests/ClaudeCode2.0-FieldSupportTests-2025_12_04.md` into `docs/history/` and keep linked planning docs in place.
- **Folder reorganization**: 
  - Consolidate related artifacts under coherent directories (e.g., move all design documents to a `design/` subdirectory).
  - Standardize naming conventions using kebab-case for directories and files.
  - Add an archive landing section to `docs/README.md` for dated history files.
- **BREAKING**: Moving archived files may affect any hardcoded file-path references; update docs links accordingly.

## Capabilities

### New Capabilities
- `documentation-cleanup`: Adds an archival workflow for dated documentation and test reports.
- `folder-reorganization`: Establishes a clearer documentation layout with an explicit `docs/history/` archive area.

### Modified Capabilities
- *(none)*

## Impact

- **Code**: No direct code changes; only documentation and folder layout modifications.
- **APIs**: No API changes.
- **Dependencies**: Minimal; may affect scripts that reference file paths.
- **Team**: Developers will benefit from clearer, up-to-date documentation and a more organized repository structure.
