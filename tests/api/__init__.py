"""
API tests for direct Bedrock interaction.

These tests hit SAP AI Core Bedrock DIRECTLY using the SDK and account_key.json,
NOT via the proxy server. They verify backend behavior and field support.

Use these to:
- Test what fields Bedrock actually supports/rejects
- Debug backend issues
- Validate SDK integration

For testing the proxy itself, see tests/integration/
"""
