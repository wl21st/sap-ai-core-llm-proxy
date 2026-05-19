"""
Smoke tests for primary API routes after dead-code cleanup.

These tests intentionally keep assertions light. They verify the three routes
still respond without crashing after the cleanup work removed unused imports
and dead code.
"""

import pytest


@pytest.mark.integration
@pytest.mark.real
@pytest.mark.smoke
class TestCleanupSmoke:
    async def test_chat_completions_smoke(self, proxy_client, proxy_url):
        response = await proxy_client.post(
            f"{proxy_url}/v1/chat/completions",
            json={
                "model": "gpt-4.1",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )

        assert response.status_code != 500

    async def test_messages_smoke(self, proxy_client, proxy_url):
        response = await proxy_client.post(
            f"{proxy_url}/v1/messages",
            json={
                "model": "anthropic--claude-4.5-sonnet",
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 16,
                "stream": False,
            },
        )

        assert response.status_code != 500

    async def test_models_smoke(self, proxy_client, proxy_url):
        response = await proxy_client.get(f"{proxy_url}/v1/models")

        assert response.status_code != 500
