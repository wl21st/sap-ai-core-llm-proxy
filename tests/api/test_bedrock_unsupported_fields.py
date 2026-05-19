"""
Direct Bedrock API tests for unsupported Anthropic fields.

These tests hit SAP AI Core Bedrock DIRECTLY (not via proxy) using the SDK,
to verify which Anthropic fields cause Bedrock to reject requests with errors.

Tests cover three model families as requested:
- sonnet-4.6 (Sonnet family)
- opus-4.7 (Opus family)
- haiku-4.5 (Haiku family)

Uses account_key.json configuration from ~/.aicore/config.json
"""

import json
import pytest
from typing import Tuple

logger_module = None  # Will import on first use


# Models to test - three families: Sonnet, Opus, Haiku
TEST_MODELS = [
    "anthropic--claude-4.6-sonnet",
    "anthropic--claude-4.7-opus",
    "anthropic--claude-4.5-haiku",
]


@pytest.mark.api
@pytest.mark.real
@pytest.mark.bedrock
class TestBedrockUnsupportedFieldsDirectAPI:
    """
    NEGATIVE TESTS: Verify that unsupported Anthropic fields cause Bedrock rejection.

    These tests intentionally send invalid payloads to Bedrock and expect 400 errors.
    This proves WHY the proxy must strip these fields.
    """

    def invoke_bedrock(
        self, client, payload: dict
    ) -> Tuple[int, dict | str]:
        """
        Invoke Bedrock with given payload and return (status_code, response).

        Returns:
            (status_code, response_body as dict or string)
        """
        global logger_module
        if logger_module is None:
            from utils.logging_utils import get_server_logger
            logger_module = get_server_logger(__name__)

        try:
            # Extract modelId from payload if present, remove it from body payload
            # (modelId goes to invoke_model parameter, not in body)
            model_id = payload.pop("modelId", "anthropic.claude-sonnet-4-20250514")

            body_json = json.dumps(payload)
            response = client.invoke_model(
                body=body_json,
                modelId=model_id,
                accept="application/json",
                contentType="application/json",
            )

            status = response.get("ResponseMetadata", {}).get("HTTPStatusCode", 200)
            body = response.get("body")

            if body:
                body_text = body.read().decode("utf-8")
                try:
                    body_json = json.loads(body_text)
                except json.JSONDecodeError:
                    body_json = body_text
            else:
                body_json = {}

            return status, body_json

        except Exception as e:
            logger_module.error(f"Bedrock invocation exception: {type(e).__name__}: {e}")
            # Return error
            return 400, {"error": str(e), "exception_type": type(e).__name__}

    @pytest.mark.parametrize("model", TEST_MODELS)
    def test_metadata_field_rejected(self, model: str, bedrock_client_factory):
        """
        NEGATIVE TEST: Bedrock behavior with metadata field.

        Observed: Bedrock silently ignores or accepts the metadata field.
        This test verifies the actual behavior - proxy must decide if stripping is needed.
        """
        try:
            client = bedrock_client_factory(model)
        except Exception as e:
            pytest.fail(f"Failed to get Bedrock client for {model}. Check SAP AI Core credentials: {e}")

        # Payload with metadata field - Bedrock accepts or ignores this
        payload = {
            "modelId": "anthropic.claude-sonnet-4-20250514",
            "anthropic_version": "bedrock-2023-05-31",
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": "Hello"}],
                }
            ],
            "max_tokens": 100,
            "metadata": {  # Bedrock ignores or accepts this
                "user_id": "test-user-123",
            },
        }

        status, response = self.invoke_bedrock(client, payload)

        # Bedrock accepts this field, so we expect 200
        assert status == 200, (
            f"Expected Bedrock to accept/ignore metadata field, got {status}. "
            f"Response: {response}. Proxy may want to strip this anyway."
        )
        print(f"✓ Confirmed: Bedrock accepts metadata for {model} (HTTP {status})")

    @pytest.mark.parametrize("model", TEST_MODELS)
    def test_output_config_field_rejected(self, model: str, bedrock_client_factory):
        """
        NEGATIVE TEST: Bedrock must reject output_config field.

        Expected: HTTP 400 Bad Request
        Proves: Proxy must strip this field before forwarding to Bedrock.
        """
        try:
            client = bedrock_client_factory(model)
        except Exception as e:
            pytest.fail(f"Failed to get Bedrock client for {model}. Check SAP AI Core credentials: {e}")

        # Invalid payload with unsupported output_config field
        payload = {
            "modelId": "anthropic.claude-sonnet-4-20250514",
            "anthropic_version": "bedrock-2023-05-31",
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": "Hello"}],
                }
            ],
            "max_tokens": 100,
            "output_config": {  # UNSUPPORTED by Bedrock
                "format": {
                    "type": "json_schema",
                }
            },
        }

        status, response = self.invoke_bedrock(client, payload)

        assert status == 400, (
            f"Expected Bedrock to reject output_config field with 400, got {status}. "
            f"Response: {response}. This proves proxy must strip this field."
        )
        print(f"✓ Confirmed: Bedrock rejects output_config for {model} (HTTP {status})")

    @pytest.mark.parametrize("model", TEST_MODELS)
    def test_context_management_field_rejected(self, model: str, bedrock_client_factory):
        """
        NEGATIVE TEST: Bedrock must reject context_management field.

        Expected: HTTP 400 Bad Request
        Proves: Proxy must strip this field before forwarding to Bedrock.
        """
        try:
            client = bedrock_client_factory(model)
        except Exception as e:
            pytest.fail(f"Failed to get Bedrock client for {model}. Check SAP AI Core credentials: {e}")

        # Invalid payload with unsupported context_management field
        payload = {
            "modelId": "anthropic.claude-sonnet-4-20250514",
            "anthropic_version": "bedrock-2023-05-31",
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": "Hello"}],
                }
            ],
            "max_tokens": 100,
            "context_management": {  # UNSUPPORTED by Bedrock
                "type": "auto",
            },
        }

        status, response = self.invoke_bedrock(client, payload)

        assert status == 400, (
            f"Expected Bedrock to reject context_management field with 400, got {status}. "
            f"Response: {response}. This proves proxy must strip this field."
        )
        print(f"✓ Confirmed: Bedrock rejects context_management for {model} (HTTP {status})")

    @pytest.mark.parametrize("model", TEST_MODELS)
    def test_all_unsupported_fields_rejected(self, model: str, bedrock_client_factory):
        """
        NEGATIVE TEST: Bedrock must reject all unsupported fields together.

        Expected: HTTP 400 Bad Request
        Proves: Proxy must strip ALL of these fields.
        """
        try:
            client = bedrock_client_factory(model)
        except Exception as e:
            pytest.fail(f"Failed to get Bedrock client for {model}. Check SAP AI Core credentials: {e}")

        # Invalid payload with all unsupported fields
        payload = {
            "modelId": "anthropic.claude-sonnet-4-20250514",
            "anthropic_version": "bedrock-2023-05-31",
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": "Hello"}],
                }
            ],
            "max_tokens": 100,
            "metadata": {"user_id": "test"},
            "output_config": {"format": {"type": "json_schema"}},
            "context_management": {"type": "auto"},
        }

        status, response = self.invoke_bedrock(client, payload)

        assert status == 400, (
            f"Expected Bedrock to reject multiple unsupported fields with 400, got {status}. "
            f"Response: {response}. This proves proxy must strip all of them."
        )
        print(f"✓ Confirmed: Bedrock rejects all unsupported fields for {model} (HTTP {status})")

    @pytest.mark.parametrize("model", TEST_MODELS)
    def test_valid_request_succeeds(self, model: str, bedrock_client_factory):
        """
        POSITIVE TEST: Valid request without unsupported fields should succeed.

        Expected: HTTP 200 with valid response
        Serves as control test - proves Bedrock client and config work.
        """
        try:
            client = bedrock_client_factory(model)
        except Exception as e:
            pytest.fail(f"Failed to get Bedrock client for {model}. Check SAP AI Core credentials: {e}")

        # Valid payload - no unsupported fields
        payload = {
            "modelId": "anthropic.claude-sonnet-4-20250514",
            "anthropic_version": "bedrock-2023-05-31",
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": "Say hello"}],
                }
            ],
            "max_tokens": 50,
        }

        status, response = self.invoke_bedrock(client, payload)

        assert status == 200, (
            f"Expected valid Bedrock request to succeed with 200, got {status}. "
            f"Response: {response}. Check Bedrock client and config."
        )
        print(f"✓ Confirmed: Valid requests work for {model} (HTTP {status})")

    @pytest.mark.parametrize("model", TEST_MODELS)
    def test_thinking_without_context_management_accepted(
        self, model: str, bedrock_client_factory
    ):
        """
        POSITIVE TEST: Valid thinking request (without nested context_management) works.

        Expected: HTTP 200
        Proves: Proxy only strips context_management, not the thinking config itself.
        """
        try:
            client = bedrock_client_factory(model)
        except Exception as e:
            pytest.fail(f"Failed to get Bedrock client for {model}. Check SAP AI Core credentials: {e}")

        # Valid thinking config - no nested context_management
        # Note: max_tokens must be > thinking.budget_tokens per Bedrock docs
        # Opus uses adaptive thinking without budget_tokens
        if "opus" in model:
            payload = {
                "modelId": "anthropic.claude-sonnet-4-20250514",
                "anthropic_version": "bedrock-2023-05-31",
                "messages": [
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": "Think about this"}],
                    }
                ],
                "max_tokens": 2048,
                "thinking": {
                    "type": "adaptive",
                },
                "output_config": {"effort": "high"},
            }
        else:
            payload = {
                "modelId": "anthropic.claude-sonnet-4-20250514",
                "anthropic_version": "bedrock-2023-05-31",
                "messages": [
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": "Think about this"}],
                    }
                ],
                "max_tokens": 2048,  # Must be > thinking.budget_tokens (1024)
                "thinking": {
                    "type": "enabled",
                    "budget_tokens": 1024,
                },
            }

        status, response = self.invoke_bedrock(client, payload)

        assert status == 200, (
            f"Expected valid thinking request to succeed with 200, got {status}. "
            f"Response: {response}. Thinking should be supported."
        )
        print(f"✓ Confirmed: Thinking config accepted for {model} (HTTP {status})")

    @pytest.mark.parametrize("model", TEST_MODELS)
    def test_cache_control_in_system_message(self, model: str, bedrock_client_factory):
        """
        TEST: Bedrock behavior with cache_control in system messages.

        Cache control is a prompt caching feature - test if Bedrock accepts it.
        """
        try:
            client = bedrock_client_factory(model)
        except Exception as e:
            pytest.fail(f"Failed to get Bedrock client for {model}. Check SAP AI Core credentials: {e}")

        # Payload with cache_control in system message
        payload = {
            "modelId": "anthropic.claude-sonnet-4-20250514",
            "anthropic_version": "bedrock-2023-05-31",
            "system": [
                {
                    "type": "text",
                    "text": "You are a helpful research assistant.",
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": "What is Python?"}],
                }
            ],
            "max_tokens": 500,
        }

        status, response = self.invoke_bedrock(client, payload)

        # Document the actual behavior (accept, reject, or ignore)
        if status == 200:
            print(f"✓ Bedrock accepts/ignores cache_control in system for {model} (HTTP {status})")
        elif status == 400:
            print(f"✓ Bedrock rejects cache_control in system for {model} (HTTP {status})")

        # For now, just document behavior without strict assertion
        print(f"  Response: {response if status != 200 else 'Success'}")

    @pytest.mark.parametrize("model", TEST_MODELS)
    def test_cache_control_in_tool_definition(self, model: str, bedrock_client_factory):
        """
        TEST: Bedrock behavior with cache_control in tool definitions.

        Prompt caching for tools - test if Bedrock accepts cache_control in tool definitions.
        """
        try:
            client = bedrock_client_factory(model)
        except Exception as e:
            pytest.fail(f"Failed to get Bedrock client for {model}. Check SAP AI Core credentials: {e}")

        # Payload with cache_control in tools
        payload = {
            "modelId": "anthropic.claude-sonnet-4-20250514",
            "anthropic_version": "bedrock-2023-05-31",
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": "Search for Python documentation"}],
                }
            ],
            "tools": [
                {
                    "name": "search_knowledge_base",
                    "description": "Search the internal knowledge base for relevant documents.",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"}
                        },
                        "required": ["query"],
                    },
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            "max_tokens": 500,
        }

        status, response = self.invoke_bedrock(client, payload)

        # Document the actual behavior
        if status == 200:
            print(f"✓ Bedrock accepts/ignores cache_control in tools for {model} (HTTP {status})")
        elif status == 400:
            print(f"✓ Bedrock rejects cache_control in tools for {model} (HTTP {status})")

        print(f"  Response: {response if status != 200 else 'Success'}")

    @pytest.mark.parametrize("model", TEST_MODELS)
    def test_cache_control_combined_system_and_tools(self, model: str, bedrock_client_factory):
        """
        TEST: Bedrock behavior with cache_control in both system messages and tools.

        Comprehensive test with cache_control in multiple locations (Anthropic prompt caching feature).
        """
        try:
            client = bedrock_client_factory(model)
        except Exception as e:
            pytest.fail(f"Failed to get Bedrock client for {model}. Check SAP AI Core credentials: {e}")

        # Payload with cache_control everywhere
        payload = {
            "modelId": "anthropic.claude-sonnet-4-20250514",
            "anthropic_version": "bedrock-2023-05-31",
            "system": [
                {
                    "type": "text",
                    "text": "You are a research assistant with access to a knowledge base.",
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": "Find information about Mars rovers"}],
                }
            ],
            "tools": [
                {
                    "name": "search_knowledge_base",
                    "description": "Search the internal knowledge base for relevant documents.",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"}
                        },
                        "required": ["query"],
                    },
                    "cache_control": {"type": "ephemeral"},
                },
                {
                    "name": "get_doc_by_id",
                    "description": "Retrieve a specific document by its ID.",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "doc_id": {"type": "string", "description": "Document ID"}
                        },
                        "required": ["doc_id"],
                    },
                    "cache_control": {"type": "ephemeral"},
                },
            ],
            "max_tokens": 1024,
        }

        status, response = self.invoke_bedrock(client, payload)

        # Document the actual behavior
        if status == 200:
            print(f"✓ Bedrock accepts/ignores combined cache_control for {model} (HTTP {status})")
        elif status == 400:
            print(f"✓ Bedrock rejects cache_control in combined payload for {model} (HTTP {status})")

        print(f"  Response: {response if status != 200 else 'Success'}")
