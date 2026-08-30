# Using SAP AI Core LLM Proxy with uvx

`uvx` is a command execution tool from Astral's `uv` ecosystem that runs Python applications directly without requiring global installation.

---

## 1. Prerequisites

Install `uv`:
```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

---

## 2. Running the Proxy Server

### Local Development
```bash
# Standard mode
uvx --from . sap-ai-proxy --config config.json

# Debug mode (verbose logs)
uvx --from . sap-ai-proxy --config config.json --debug
```

### Directly from GitHub
```bash
uvx --from git+https://github.com/wl21st/sap-ai-core-llm-proxy sap-ai-proxy --config config.json
```

---

## 3. CLI Options

```
sap-ai-proxy [OPTIONS]

Options:
  -c, --config PATH    Path to configuration file (required)
  -d, --debug          Enable debug logging
  -h, --help           Show this message and exit
```

---

## 4. Alternative Execution Methods

```bash
# Development with uv virtual environment
uv sync
uv run python main.py --config config.json

# Python direct run
python main.py --config config.json
```
