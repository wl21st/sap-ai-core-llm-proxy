## Context

The docs tree mixes active references with dated history files. That makes it harder to tell which material should be used for implementation guidance and which files are archival records.

## Goals / Non-Goals

**Goals:**
- Separate dated history from active documentation.
- Make navigation in `docs/README.md` reflect the current folder structure.
- Keep the change limited to documentation and path organization.

**Non-Goals:**
- Changing runtime code or API behavior.
- Introducing new documentation tooling.
- Rewriting the content of active docs beyond path cleanup.

## Decisions

- **Archive dated docs in `docs/history/`**: This keeps stale material discoverable without making it look current.
- **Keep README as the primary index**: The README should remain the entry point for docs discovery rather than adding another index layer.
- **Avoid broad renames**: Only move or rename files where it improves clarity and does not create unnecessary churn.

## Risks / Trade-offs

- Archived files may still be linked elsewhere → update links and verify references after moves.
- Folder cleanup can create short-term navigation confusion → document the structure clearly in `docs/README.md`.

## Migration Plan

- Review existing docs for dated or duplicate material.
- Move confirmed history files into `docs/history/`.
- Update `docs/README.md` to point at the new structure.
- Verify repository references to moved files.

## Open Questions

- Should additional dated docs be moved into history during this change?
- Are there any external references that need coordinated updates?
