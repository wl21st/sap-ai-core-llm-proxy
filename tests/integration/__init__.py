"""
Real integration tests for SAP AI Core LLM Proxy.

These tests run against an actual proxy server instance (typically localhost)
and validate end-to-end functionality including:
- Model listing
- Chat completions (streaming and non-streaming)
- Claude Messages API
- Token usage
- SSE format validation
- Response format validation

To run these tests:
    pytest tests/integration/ -m real -v

To skip if server not running:
    pytest tests/integration/ -m real --skip-if-server-down
"""