# Using SAP AI Core LLM Proxy with uvx

## Overview

The SAP AI Core LLM Proxy can be run using `uvx`, a tool from the `uv` package manager that allows you to run Python applications without installing them first. This is the recommended method for running the proxy server.

## What is uvx?

`uvx` is a command execution tool from the `uv` ecosystem that:
- Runs Python applications without requiring installation
- Automatically manages dependencies in isolated environments
- Provides a clean, reproducible execution environment
- Works similar to `npx` for Node.js

## Prerequisites

Install `uv` if you haven't already:

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Or using pip
pip install uv
```

## Running the Proxy Server

### Local Development (from repository)

When working with the repository locally:

```bash
# Standard mode
uvx --from . sap-ai-proxy --config config.json

# Debug mode (detailed logging)
uvx --from . sap-ai-proxy --config config.json --debug

# With custom host and port
uvx --from . sap-ai-proxy --config config.json
```

The `--from .` flag tells `uvx` to use the local package in the current directory.

### After Publishing to PyPI

Once published to PyPI, you can run from anywhere:

```bash
# Run the latest version
uvx sap-ai-proxy --config config.json

# Run a specific version
uvx --from sap-ai-core-llm-proxy==1.2.2 sap-ai-proxy --config config.json

# Run with debug mode
uvx sap-ai-proxy --config /path/to/config.json --debug
```

## Available Commands

The `sap-ai-proxy` command accepts the following arguments:

```bash
sap-ai-proxy [OPTIONS]

Options:
  --config PATH    Path to configuration file (required)
  --debug          Enable debug mode with detailed logging
  --help           Show help message and exit
```

## Configuration

The proxy requires a `config.json` file with your SAP AI Core credentials and model deployments. See the main README for configuration details.

Example minimal command:
```bash
uvx --from . sap-ai-proxy --config config.json
```

## Advantages of Using uvx

1. **No Installation Required**: Run the proxy without installing it globally
2. **Isolated Environment**: Each execution uses a clean, isolated environment
3. **Version Control**: Easily switch between different versions
4. **Reproducible**: Guaranteed consistent behavior across different machines
5. **Clean System**: No global package installations cluttering your system

## Alternative Running Methods

If you prefer traditional methods:

### Using Python Directly
```bash
python proxy_server.py --config config.json
```

### Using uv run
```bash
uv run python proxy_server.py --config config.json
```

### After Installing Locally
```bash
# Install in development mode
uv pip install -e .

# Run the installed command
sap-ai-proxy --config config.json
```

## Troubleshooting

### Command Not Found

If `uvx` is not found:
```bash
# Check if uv is installed
uv --version

# Reinstall uv
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Entry Point Error

If you get an error about the entry point:
```bash
# Ensure you're in the project directory
cd /path/to/sap-ai-core-llm-proxy

# Verify pyproject.toml has the [project.scripts] section
cat pyproject.toml | grep -A2 "\[project.scripts\]"
```

### Configuration File Not Found

Use absolute paths or ensure you're in the correct directory:
```bash
# Use absolute path
uvx --from . sap-ai-proxy --config /absolute/path/to/config.json

# Or change to the config directory
cd /path/to/config
uvx --from /path/to/sap-ai-core-llm-proxy sap-ai-proxy --config config.json
```

## Performance Notes

- First run may be slower as `uvx` sets up the environment
- Subsequent runs are faster due to caching
- Performance is identical to running via `python` after the initial setup

## See Also

- [uv Documentation](https://github.com/astral-sh/uv)
- [Main README](../README.md)
- [Configuration Guide](../README.md#configuration)
- [Release Workflow](./RELEASE_WORKFLOW.md)
