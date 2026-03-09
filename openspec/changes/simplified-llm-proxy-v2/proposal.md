## Why

The current `sap-ai-core-llm-proxy` (~7,180 lines) spends ~40% of its codebase on cross-vendor format conversion (OpenAI ↔ Claude ↔ Gemini), which creates a maintenance burden as vendors frequently update their APIs. A new, simplified proxy is needed that **exposes each vendor's native API format with minimal normalization** — no cross-vendor translation. This eliminates the largest source of complexity and frequent update requirements. Additionally, the current proxy requires manually specifying deployment URLs per model per subaccount in config; using the SAP AI Core deployment API for auto-discovery will dramatically simplify setup. A modern admin GUI (cockpit) is a priority for ease of management.

## What Changes

This is a **new standalone project** (separate repository), not a modification to the existing proxy.

- **New project**: Clean-room FastAPI-based proxy with minimal codebase
- **No cross-vendor conversion**: Each vendor endpoint exposes its native API format — OpenAI requests go to OpenAI models, Anthropic requests go to Claude models, Gemini requests go to Gemini models
- **Minimal normalization only**: Fix SAP AI Core-specific quirks (e.g., header mapping, auth injection) but preserve native request/response formats
- **Auto-discovery via SAP AI Core API**: Use `GET /v2/lm/deployments` to automatically discover available models from service keys — no manual deployment URL configuration
- **Curated model list**: Expose only well-known, production-ready models (Claude 4.x, GPT-4o/o3, Gemini 2.5) plus embedding APIs (OpenAI `text-embedding-3-*`, Gemini `embedding-001`)
- **Admin GUI cockpit**: Tauri v2 desktop application with Rust backend and React/TypeScript frontend, inspired by [Antigravity Manager](https://github.com/lbjlaq/Antigravity-Manager) (25.6k★, Ant Design) and [Cockpit Tools](https://github.com/jlcodes99/cockpit-tools) (1.2k★, DaisyUI). Provides configuration management, model status, and monitoring. Architecture: Tauri v2 shell → Rust backend (axum HTTP server, reqwest HTTP client, rusqlite for local config, tokio async) → React/Vite frontend (Zustand state, Tailwind CSS, modern component library)
- **Simplified configuration**: Single service key JSON → auto-populated model catalog

### Supported Endpoints (Native Format Pass-Through)

| Route | Target Vendor | Format |
|-------|--------------|--------|
| `POST /v1/chat/completions` | OpenAI models (GPT-4o, o3) | OpenAI native |
| `POST /v1/embeddings` | OpenAI embedding models | OpenAI native |
| `POST /v1/messages` | Anthropic models (Claude 4.x) | Anthropic native |
| `POST /v1/models` | All vendors | Unified model list |
| `POST /gemini/v1beta/models/{m}:generateContent` | Gemini models | Gemini native |
| `POST /gemini/v1beta/models/{m}:streamGenerateContent` | Gemini models | Gemini native |
| `POST /gemini/v1beta/models/{m}:embedContent` | Gemini embeddings | Gemini native |

## Capabilities

### New Capabilities

- `native-openai-proxy`: Pass-through proxy for OpenAI-format endpoints (`/v1/chat/completions`, `/v1/embeddings`) with SAP AI Core auth injection and minimal normalization. Supports streaming (SSE).
- `native-anthropic-proxy`: Pass-through proxy for Anthropic Messages API (`/v1/messages`) with SAP AI Core auth injection. Supports streaming (SSE).
- `native-gemini-proxy`: Pass-through proxy for Gemini API endpoints (`generateContent`, `streamGenerateContent`, `embedContent`) with SAP AI Core auth injection.
- `sap-aicore-autodiscovery`: Auto-discover available models and deployment URLs from SAP AI Core service keys using the deployment listing API (`GET /v2/lm/deployments`). Replaces manual URL configuration.
- `proxy-auth-and-tokens`: Bearer token authentication for proxy clients, plus SAP AI Core OAuth token management (fetch, cache, auto-refresh) per service key.
- `model-catalog`: Unified model catalog aggregating discovered models across all configured service keys, with curated well-known model filtering. Powers the `/v1/models` endpoint.
- `admin-cockpit`: Tauri v2 desktop application for managing service keys, viewing discovered models, monitoring proxy status, and configuring settings. Follows the architecture pattern of Antigravity Manager and Cockpit Tools: Tauri v2 + Rust backend (axum, reqwest, rusqlite, tokio) + React/TypeScript frontend (Vite, Zustand, Tailwind + Ant Design or DaisyUI). The desktop app manages the proxy server lifecycle and communicates with the FastAPI proxy backend via local HTTP/SSE.
- `project-foundation`: New standalone project scaffolding — two sub-projects: (1) FastAPI proxy backend with Python project structure, Docker support, CI/CD, dependency management (uv/pyproject.toml), and (2) Tauri v2 desktop app with Rust/React project structure.

### Modified Capabilities

_(None — this is a new standalone project, not modifying the existing proxy.)_

## Impact

- **New repository**: Separate project, no impact on existing `sap-ai-core-llm-proxy`
- **Proxy dependencies**: FastAPI, uvicorn, httpx (async HTTP), Pydantic v2, SAP AI Core SDK (optional, for deployment discovery)
- **Desktop app dependencies**: Tauri v2, Rust (axum, reqwest, rusqlite, tokio, serde), React, Vite, TypeScript, Zustand, Tailwind CSS, Ant Design or DaisyUI
- **SAP AI Core API**: Requires service key with permissions to list deployments (`/v2/lm/deployments`)
- **Client compatibility**: Clients must use the correct vendor-native format for each endpoint (no cross-vendor translation available)
- **Breaking change vs current proxy**: Clients currently relying on cross-vendor translation (e.g., sending OpenAI format to Claude models) will need to switch to vendor-native format
