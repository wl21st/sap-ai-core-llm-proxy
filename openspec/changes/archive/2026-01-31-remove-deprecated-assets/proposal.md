# Change: Remove Deprecated Assets

## Why
The project contains outdated documentation and legacy code that confuse maintenance and usage. Cleaning these up improves project hygiene and directs users to the correct entry points.

## What Changes
- Remove deprecated documentation files (Phase 3/4 docs, resolved bug reports).
- Remove `archive/proxy_server_litellm.py`.
- Add a startup warning to `proxy_server.py` marking it as a legacy entry point.

## Impact
- Affected specs: cleanup
- Affected code: `proxy_server.py`, `archive/proxy_server_litellm.py`, `docs/`