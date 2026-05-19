## ADDED Requirements

### Requirement: Documentation folders are purpose grouped
The documentation layout MUST group files by purpose so contributors can find architecture, configuration, testing, and history material without ambiguity.

#### Scenario: Contributor browses docs tree
- **WHEN** a contributor inspects the docs directory structure
- **THEN** each major folder MUST correspond to a clear documentation purpose

### Requirement: Archived files use stable history naming
Archived documentation files MUST use names that make their historical nature obvious.

#### Scenario: Archived file name is read
- **WHEN** a file is stored under `docs/history/`
- **THEN** its name MUST clearly indicate it is historical or dated
