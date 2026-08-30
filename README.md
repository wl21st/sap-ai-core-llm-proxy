# SAP AI Core LLM Proxy

A high-performance, modular API gateway that transforms SAP AI Core services into OpenAI- and Anthropic-compatible endpoints with multi-subaccount round-robin load balancing.

---

## 🚀 Key Features

- **OpenAI Compatibility**: Full support for `/v1/chat/completions`, `/v1/models`, and `/v1/embeddings`.
- **Anthropic Messages API**: Native `/v1/messages` endpoint for Claude Code, Cursor, and Anthropic SDKs.
- **Multi-Model Translation**: Real-time bidirectional format translation for:
  - **OpenAI**: `gpt-4o`, `gpt-4.1`, `gpt-o3-mini`, `gpt-o3`, `gpt-o4-mini`
  - **Anthropic Claude**: `claude-3.5-sonnet`, `claude-3.7-sonnet`, `claude-4.5-sonnet` (via AWS Bedrock)
  - **Google Gemini**: `gemini-1.5-pro`, `gemini-2.5-pro` (via Google Vertex AI)
- **Multi-Subaccount Load Balancing**: Automatic round-robin distribution and failover across accounts and deployments.
- **Real-Time Streaming**: Server-Sent Events (SSE) streaming with accurate token accounting and prompt caching.
- **Automated Validation**: Startup checks for model family, version, and deployment mismatches.

---

## ⚡ Quick Start

### 1. Run with `uvx` (Recommended — No Installation Required)

```bash
# Run locally from repository
uvx --from . sap-ai-proxy -c config.json

# Run with debug logging
uvx --from . sap-ai-proxy -c config.json -d

# Run directly from GitHub
uvx --from git+https://github.com/wl21st/sap-ai-core-llm-proxy sap-ai-proxy -c config.json
```

### 2. Configuration (`config.json`)

Create your `config.json` (copy from `config.json.example`):

```json
{
  "subAccounts": {
    "account1": {
      "resource_group": "default",
      "service_key_json": "service_key.json",
      "deployment_models": {
        "gpt-4o": [
          "https://api.ai.prod.eu-central-1.aws.ml.hana.ondemand.com/v2/inference/deployments/d111"
        ],
        "anthropic--claude-4.5-sonnet": [
          "https://api.ai.prod.eu-central-1.aws.ml.hana.ondemand.com/v2/inference/deployments/d222"
        ]
      }
    }
  },
  "secret_authentication_tokens": ["sk-my-secret-token"],
  "host": "127.0.0.1",
  "port": 3001
}
```

---

## 📡 API Endpoints

Once the proxy is running (default: `http://127.0.0.1:3001`):

| Endpoint | Protocol | Description |
|---|---|---|
| `POST /v1/chat/completions` | OpenAI | Chat completions (streaming & non-streaming) |
| `POST /v1/messages` | Anthropic | Claude Messages API (streaming & non-streaming) |
| `GET /v1/models` | OpenAI | List configured and active models |
| `POST /v1/embeddings` | OpenAI | Text embeddings |
| `GET /health`, `/info`, `/stats` | Observability | Health check, server info, and request metrics |

---

## 🛠️ Client Integrations

### Claude Code
```bash
export ANTHROPIC_AUTH_TOKEN=sk-my-secret-token
export ANTHROPIC_BASE_URL=http://127.0.0.1:3001
export ANTHROPIC_MODEL=anthropic--claude-4.5-sonnet
claude
```

### Cursor / OpenAI Clients
- **Base URL**: `http://127.0.0.1:3001/v1`
- **API Key**: `sk-my-secret-token`
- **Model**: `gpt-4o` or configured model alias

---

## 📖 Documentation

Comprehensive guides and technical documentation are available in the [`docs/`](./docs/README.md) directory:

- 🏗️ **Architecture**:
  - [System Architecture](./docs/architecture/architecture.md)
  - [Technical Debt Assessment](./docs/architecture/technical-debt.md)
  - [Streaming & SSE Analysis](./docs/architecture/streaming-sse-analysis.md)
  - [SAP AI Core API Reference](./docs/architecture/sapaicore-api.md)
- ⚙️ **Configuration & Ops**:
  - [Configuration Validation & Filtering](./docs/configuration/config-validation.md)
  - [Logging System & Keywords](./docs/configuration/logging-system.md)
  - [Troubleshooting Guide](./docs/guides/troubleshooting.md)
- 📚 **Guides**:
  - [Using with uvx](./docs/guides/uvx-usage.md)
  - [Release & Build Workflows](./docs/guides/release-quick-start.md)
  - [Python Conventions & Scoping](./docs/guides/python-conventions.md)
- 🧪 **Testing**:
  - [Testing Guide](./docs/testing/testing.md)
  - [Direct Bedrock API Tests](./tests/api/README.md)
  - [Integration Tests](./tests/integration/README.md)

---

## 🧪 Development & Testing

```bash
# Install development dependencies
uv sync --group dev

# Run unit tests
uv run pytest tests/unit/ -v

# Run integration tests (proxy running on localhost)
make test-integration

# Build standalone binary with PyInstaller
make build-tested
```

---

## 📄 License

This project is licensed under the MIT License.
