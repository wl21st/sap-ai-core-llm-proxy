# SAP AI Core LLM Proxy - Development Backlog

This document tracks planned improvements, active initiatives, and roadmap items for the SAP AI Core LLM Proxy project.

---

## Roadmap & Active Initiatives

| # | Item | Category | Priority | Status |
|---|---|---|---|---|
| 1 | **Multi-Tenant SDK Pool Isolation** | Architecture / Security | Critical (P0) | 🔴 To Do |
| 2 | **Thread-Safe LoadBalancer Encapsulation** | Concurrency | High (P1) | 🔴 To Do |
| 3 | **Converter Package & Facade Extraction** | SOLID Architecture | High (P1) | 🟡 In Progress |
| 4 | **Model Manifest & Neutral Adapter Plan** | Extensibility | High (P1) | 🟡 In Progress |
| 5 | **Unified Async HTTP Client Pool** | Networking / Performance | Medium (P2) | 🔴 To Do |
| 6 | **Unskip & Fix Router Unit Tests** | Quality Assurance | High (P1) | 🔴 To Do |
| 7 | **Dynamic Model Normalization Config** | Configuration | Medium (P2) | 🔴 To Do |

---

## Completed Initiatives

- ✅ **FastAPI Modular Migration**: Decomposed monolithic proxy into modular routers (`routers/chat.py`, `routers/messages.py`, `routers/models.py`, `routers/status.py`).
- ✅ **TLS Auto-Discovery & Recovery**: Automatic certifi and system CA certificate fallback with Bedrock session invalidation on certificate rotation.
- ✅ **Prompt Caching Support**: Preserved `cache_control` pass-through for Anthropic `/v1/messages` and normalized May 2026 Bedrock cache creation tokens.
- ✅ **Unsupported Field Stripping**: Automatic sanitization of Anthropic `metadata`, `output_config`, and `context_management` fields before Bedrock dispatch.
- ✅ **Automated Test Suite**: 600+ unit and integration tests with pytest and uv.
