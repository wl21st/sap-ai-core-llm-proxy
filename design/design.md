## Context

The repository contains outdated documentation and a fragmented folder structure, causing confusion for developers seeking accurate implementation guidance. Key issues include duplicate examples, stale API guides, and inconsistent directory naming, which hinder onboarding and maintenance.

## Goals / Non-Gr

## Goals / Non-Goals

**Goals:**
- Remove or update obsolete design documents and deprecated API guides.
- Consolidate related artifacts under coherent directories (e.g., move design documents to a `design/` subdirectory).
- Standardize naming conventions using kebab-case for directories and files.
- Delete redundant or duplicate files after stakeholder review.

**Non-Goals:**
- Changing runtime behavior of the proxy server.
- Modifying API contracts or adding new features.
- Direct code modifications beyond documentation and structure.

## Decisions

- **Consolidate Documentation**: Create a `design/` directory to house all design-related documents.
- **Naming Convention**: Use kebab-case for all directory and file names (e.g., `documentation-cleanup`, `folder-reorganization`).
- **Retention Policy**: Keep documents that are actively referenced; archive others with a `DEPRECATED` badge.
- **Structure**: Organize documents by purpose: `documentation-cleanup` and `folder-reorganization` as subsections.
- **Process**: Establish a review step with SIG to approve deletions.

## Risks / Trade-offs

- **Risk**: Removing a document that is still in use.
  - **Mitigation**: Conduct a usage audit and keep a backup of removed files in an archive branch.
- **Risk**: Potential confusion during transition.
  - **Mitigation**: Update internal wiki to reflect new structure and provide migration guidelines.

## Migration Plan

- Communicate changes to the team via a notification.
- Update any internal scripts that reference file paths.
- Archive removed files in a separate git branch for reference.
- Verify that all links in remaining documentation work correctly.

## Open Questions

- Should we keep the old `openspec/AGENTS.md` file for historical reference?
- How do we handle external contributors who reference outdated docs?