## Why

The current proxy is a Python-only CLI daemon requiring a config file and a running server process. Popular tools like Antigravity Manager (25k stars, Tauri v2 + Rust + React) and Cockpit Tools (1.2k stars, same stack) show that users increasingly expect **desktop-native, GUI-driven account/proxy managers** with zero-config onboarding. Investigating their tech stack now positions the next major version (v2) to decide whether to adopt a similar native-app architecture, or to stay server-side but adopt modern async/Rust tooling for performance.

## What Changes

- Produce a technology audit comparing the current Python/Flask/FastAPI stack against the Tauri v2 + Rust + React pattern used by Antigravity Manager and Cockpit Tools.
- Identify which architectural patterns from these tools are directly applicable to a simplified proxy (account switching, quota monitoring, multi-instance management, SSE streaming).
- Evaluate whether the next major version should remain a headless Python server, become a Tauri desktop app, or adopt a hybrid model (Rust core + optional GUI).
- Document the dependency surface differences: current stack (Python 3.13, FastAPI, uvicorn, SAP AI SDK, botocore) vs candidate stack (Rust/Axum, Tauri v2, React/Vite, SQLite via rusqlite).
- Identify migration risks and breaking changes for existing `config.json`-based deployments.

## Capabilities

### New Capabilities

- `tech-stack-audit`: Structured comparison of current Python stack vs Tauri/Rust/React pattern — covering runtime, packaging, IPC, streaming (SSE/WebSocket), multi-account storage, and cross-platform distribution.
- `simplified-proxy-architecture-options`: Decision matrix for the v2 architecture: headless Python (refactored), Rust/Axum server, Tauri desktop app, or hybrid.

### Modified Capabilities

<!-- No existing spec-level behavior is changing — this is a pure investigation. -->

## Impact

- No code changes in this iteration; outputs are design/research artifacts only.
- Findings feed directly into the `fastapi-core`, `async-networking`, `api-routes`, and `caching-and-config` specs for v2 planning.
- Affects packaging strategy: current PyInstaller binary vs potential Tauri `.dmg`/`.exe`/`.AppImage` distribution.
- Affects deployment model: headless server (current) vs tray-icon desktop app (Antigravity/Cockpit pattern).
