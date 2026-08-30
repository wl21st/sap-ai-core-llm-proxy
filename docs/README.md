# SAP AI Core LLM Proxy — Documentation

Welcome to the documentation for the SAP AI Core LLM Proxy.

---

## 📋 Documentation Index

### 🏗️ [Architecture](./architecture/)
System design, component relationships, API specifications, and technical debt assessments.
- **[System Architecture](./architecture/architecture.md)** — Core components, FastAPI routers, and proxy lifecycle.
- **[SAP AI Core Hub API Reference](./architecture/sapaicore-api.md)** — Upstream endpoint specs for OpenAI, Claude, and Gemini on SAP AI Core.
- **[Streaming & SSE Analysis](./architecture/streaming-sse-analysis.md)** — Server-Sent Events protocols and cross-provider streaming transforms.
- **[Technical Debt & Refactoring Roadmap](./architecture/technical-debt.md)** — Critical debt analysis and SOLID converter extraction plan.

### ⚙️ [Configuration](./configuration/)
Setup, configuration models, deployment validation, and structured logging.
- **[Configuration Validation & Filtering](./configuration/config-validation.md)** — Startup model validation, mismatch detection, and deployment inspection.
- **[Logging System & Keywords](./configuration/logging-system.md)** — Structured logger architecture, keyword dictionary, and debugging grep commands.

### 📚 [Guides](./guides/)
Developer guides, execution instructions, release workflows, and troubleshooting.
- **[Running with uvx](./guides/uvx-usage.md)** — Recommended execution method locally and from GitHub.
- **[Troubleshooting Guide](./guides/troubleshooting.md)** — TLS certificate auto-discovery, auth error recovery, and rate limit handling.
- **[Release Quick Start & Packaging](./guides/release-quick-start.md)** — Versioning, standalone binary builds, make targets, and release steps.
- **[Python Coding Conventions](./guides/python-conventions.md)** — PEP 8 style guide, naming rules, type annotations, and module vs class scoping.

### 📖 [Reference](./reference/)
Protocol formats, token accounting, backlogs, and payload examples.
- **[Token Usage & Prompt Caching](./reference/token-usage-and-caching.md)** — Normalized usage metrics, extended thinking tokens, `cache_control` pass-through, and Bedrock wire formats.
- **[Payload Conversion Examples](./reference/payload-examples.md)** — Inbound vs outbound payloads and unsupported field stripping.
- **[Model Manifest & Neutral Adapter Plan](./reference/model-manifest-plan.md)** — Neutral adapter and declarative model manifest design.
- **[Development Backlog](./reference/backlog.md)** — Active roadmap and planned features.

### 🧪 [Testing](./testing/)
Testing guidelines, pytest markers, and test suite execution.
- **[Testing Guide](./testing/testing.md)** — Running unit, integration, and direct API test suites.
- **[Direct Bedrock API Tests](../tests/api/README.md)** — Direct Bedrock SDK test suite and unsupported field proofs.
- **[Integration Tests](../tests/integration/README.md)** — End-to-end localhost integration tests and response validators.
