## Context

Static analysis (`ruff check . --select F401,F811,F841`) identifies 47 unused imports and 11 unused local variables across the codebase. These accumulate naturally over refactoring cycles — when code is moved, extracted, or deleted, its import site is not always cleaned up. The `if False:` dead code block in `proxy_server.py` was also previously noted in `CLAUDE.md` as known technical debt.

All removals are non-behavioral: no logic, no exports consumed by callers, no runtime effects.

## Goals / Non-Goals

**Goals:**
- Remove all unused imports flagged by `ruff F401/F811` in production files
- Remove all unused imports flagged by `ruff F401/F811` in test files
- Remove unused local variable assignments flagged by `ruff F841` in test files
- Leave `make test` green after every removal

**Non-Goals:**
- Fixing other ruff violations (line length, type annotations, etc.)
- Refactoring any logic
- Touching files not flagged by the static analysis tools

## Decisions

**Use `ruff --fix` for import removals** rather than manual editing.
Ruff's auto-fix is safe for F401/F811 — it only removes the import line and never touches the rest of the file. Manual editing risks typos or leaving behind blank lines. Running `ruff check . --select F401,F811 --fix` handles all 47 cases atomically.

**Handle F841 (unused variables) manually** because ruff's unsafe-fix deletes the entire assignment statement, which could silently drop a function call with side effects (e.g., `result = mock.call()`). Each case in test files should be verified before removal.

**Production files first, test files second** — allows `make test` to be run as a checkpoint between the two groups, confirming no production behavior changed.

## Risks / Trade-offs

- **[Risk] Ruff auto-fix removes a re-exported name** → Mitigation: All flagged imports are `F401` (unused in the file itself). Re-exports would be detected via usage; confirm with `git diff` before committing.
- **[Risk] Unused variable removal changes test assertion logic** → Mitigation: Manual review of each F841 case before deletion.
- **[Risk] Test file import removal breaks a fixture or conftest dependency** → Mitigation: Run `make test` after each file group.
