## Why

The repository still contains dated documentation and duplicated planning material that is easy to confuse with current guidance. Cleaning up the docs tree will make the active references easier to find and reduce the chance that contributors follow stale instructions.

## What Changes

- Archive dated documentation into `docs/history/` and keep active reference material in purpose-specific folders.
- Update `docs/README.md` so the documentation structure clearly points to current vs archived content.
- Standardize documentation names and locations where needed so history files are easy to identify.
- **BREAKING**: Any hardcoded links or scripts referencing moved documentation paths will need updates.

## Capabilities

### New Capabilities
- `documentation-cleanup`: Adds a documented archival convention for dated docs and history files.
- `folder-reorganization`: Establishes a clearer documentation layout with explicit archive placement.

### Modified Capabilities
- *(none)*

## Impact

- Documentation entry points and README navigation.
- Links or scripts that reference archived file paths.
- Developer onboarding and maintenance workflows.
