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
    "sonnet-4.6",
    "opus-4.7",
    "haiku-4.5",
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
            body_json = json.dumps(payload)
            response = client.invoke_model(
                body=body_json,
                modelId=payload.get("modelId", "anthropic.claude-sonnet-4-20250514"),
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
        NEGATIVE TEST: Bedrock must reject metadata field.

        Expected: HTTP 400 Bad Request
        Proves: Proxy must strip this field before forwarding to Bedrock.
        """
        try:
            client = bedrock_client_factory(model)
        except Exception as e:
            pytest.fail(f"Failed to get Bedrock client for {model}. Check SAP AI Core credentials: {e}")

        # Invalid payload with unsupported metadata field
        payload = {
            "modelId": "anthropic.claude-sonnet-4-20250514",
            "anthropic_version": "bedrock-2023-05-31",
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": "Hello"}],
                }
            ],
            "max_tokens": 100,
            "metadata": {  # UNSUPPORTED by Bedrock
                "user_id": "test-user-123",
            },
        }

        status, response = self.invoke_bedrock(client, payload)

        assert status == 400, (
            f"Expected Bedrock to reject metadata field with 400, got {status}. "
            f"Response: {response}. This proves proxy must strip this field."
        )
        print(f"✓ Confirmed: Bedrock rejects metadata for {model} (HTTP {status})")

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
                    "content": [{"text": "Hello"}],
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
                    "content": [{"text": "Hello"}],
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
                    "content": [{"text": "Hello"}],
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
                    "content": [{"text": "Say hello"}],
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
        payload = {
            "modelId": "anthropic.claude-sonnet-4-20250514",
            "anthropic_version": "bedrock-2023-05-31",
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": "Think about this"}],
                }
            ],
            "max_tokens": 200,
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
