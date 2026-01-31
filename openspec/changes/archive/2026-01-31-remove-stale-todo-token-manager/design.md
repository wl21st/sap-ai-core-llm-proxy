## Context

The `TokenManager` was implemented with the 1-1 mapping to `SubAccountConfig`, but the initial TODO was left behind.

## Goals / Non-Goals

**Goals:**
- Remove the specific TODO line from `auth/token_manager.py`.

**Non-Goals:**
- Refactoring the `TokenManager` logic itself.
- Changing how `TokenManager` is instantiated.

## Decisions

### Decision 1: Direct Removal

We will directly edit the docstring to remove the line. No other code changes are required.
