# Remove Deprecated SDKs

## Goal
Remove the unused `ai-api-client-sdk` and `ai-core-sdk` dependencies from the project configuration to clean up the environment and reduce security risks.

## Context
The project `pyproject.toml` lists `ai-api-client-sdk` and `ai-core-sdk`. Code analysis confirms that these libraries are not imported or used in the current codebase. The project appears to use `requests` for direct API calls or potentially `sap-ai-sdk-gen` (though usage of that is also minimal/not found in search, it is a separate dependency tree).

`ai-core-sdk` depends on `ai-api-client-sdk`, so both must be removed to eliminate the deprecated `ai-api-client-sdk` package.

## Strategy
1.  Remove `ai-api-client-sdk` and `ai-core-sdk` from `pyproject.toml`.
2.  Update the lock file (via `uv lock`).
3.  Verify the application still functions.
