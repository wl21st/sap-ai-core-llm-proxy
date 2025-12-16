# Build stage - install dependencies
FROM python:3.13-slim AS builder

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Install uv package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies and clean up in one layer
RUN uv sync --frozen --no-dev && \
    # Remove unnecessary files
    find /app/.venv -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true && \
    find /app/.venv -type f -name "*.pyc" -delete && \
    find /app/.venv -type f -name "*.pyo" -delete && \
    find /app/.venv -type d -name "*.dist-info" -exec rm -rf {}/RECORD {} + 2>/dev/null || true && \
    find /app/.venv -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true && \
    find /app/.venv -type d -name "test" -exec rm -rf {} + 2>/dev/null || true && \
    # Remove pip, setuptools, wheel (not needed at runtime)
    uv pip uninstall pip setuptools wheel -y 2>/dev/null || true

# Runtime stage - minimal image
FROM python:3.13-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# Install only runtime dependencies and clean up in one layer
RUN apt-get update -y && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* && \
    # Remove unnecessary Python files from base image
    find /usr/local/lib/python3.13 -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true && \
    find /usr/local/lib/python3.13 -type f -name "*.pyc" -delete && \
    find /usr/local/lib/python3.13 -type f -name "*.pyo" -delete

WORKDIR /app

# Copy uv binary
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application source
COPY proxy_server.py proxy_helpers.py ./
COPY auth ./auth
COPY config ./config
COPY utils ./utils

# Expose default port
EXPOSE 3001

# Default configuration path can be overridden with CONFIG_PATH env var
ENV CONFIG_PATH=/app/config.json \
    HOST=0.0.0.0 \
    PORT=3001

# For SAP AI SDK, ~/.aicore/config.json should be mounted into /root/.aicore/config.json
# Example: -v $HOME/.aicore:/root/.aicore:ro

# Healthcheck (basic)
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -fsS http://localhost:${PORT}/v1/models || exit 1

# Start the proxy server (host/port can be changed via env)
CMD ["python", "proxy_server.py", "--config", "/app/config.json"]
