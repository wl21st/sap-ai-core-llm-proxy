## ADDED Requirements

### Requirement: Dated docs are archived
The documentation system MUST keep dated or historical documentation in `docs/history/` rather than mixing it with active reference material.

#### Scenario: Historical test report is archived
- **WHEN** a dated test report is identified for archival
- **THEN** it MUST reside under `docs/history/`

### Requirement: README distinguishes active and archived docs
The documentation index MUST clearly distinguish active documentation folders from archived history files.

#### Scenario: Reader navigates docs index
- **WHEN** a contributor opens `docs/README.md`
- **THEN** the README MUST indicate which sections are active documentation and which entries are archived history
