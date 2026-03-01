"""
Integration tests for /v1/chat/completions endpoint.

Tests chat completions (streaming and non-streaming) for all models
against a running proxy server.
"""

import json

import pytest
import requests

from tests.integration.test_validators import ResponseValidator


@pytest.mark.integration
@pytest.mark.real
@pytest.mark.parametrize(
    "model",
    [
        "anthropic--claude-4.5-sonnet",
        "sonnet-4.5",
        "gpt-4.1",
        "gpt-5",
        "gemini-2.5-pro",
    ],
)
class TestChatCompletionsNonStreaming:
    """Tests for non-streaming chat completions."""

    def test_simple_completion(self, proxy_client, proxy_url, model, max_tokens):
        """Test basic non-streaming completion."""
        # Use specific request format for different models
        if model == "gpt-5":
            request_data = {
                "model": model,
                "messages": [{"role": "user", "content": "Hello, how are you?"}],
                "max_completion_tokens": 1000,
                "stream": False,
                "reasoning_effort": "low",
            }
        elif model == "sonnet-4.5":
            request_data = {
                "model": model,
                "messages": [{"role": "user", "content": "Hello, how are you?"}],
                "max_tokens": max_tokens,
                "stream": False,  # Required for sonnet-4.5
            }
        else:
            request_data = {
                "model": model,
                "messages": [{"role": "user", "content": "Hello, how are you?"}],
                "max_tokens": max_tokens,
                "stream": False,
            }

        response = proxy_client.post(
            f"{proxy_url}/v1/chat/completions",
            json=request_data,
            stream=True if model == "sonnet-4.5" else False,
        )

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )
        data = response.json()

        # Validate response format
        ResponseValidator.validate_openai_format(data)
        ResponseValidator.validate_common_attributes(data)

        # Check content is not empty
        content = data["choices"][0]["message"]["content"]
        assert content, f"Response content is empty for model {model}"
        assert len(content) > 0, f"Response content has zero length for model {model}"

    def test_non_filtered_model_succeeds(
        self, proxy_client, proxy_url, model, max_tokens, model_filter_tests
    ):
        """Verify non-filtered models continue working with filters enabled."""
        if not model_filter_tests.get("enabled"):
            pytest.skip("Model filter integration tests are disabled")

        allowed_models = model_filter_tests.get("allowed_models", [])
        if model not in allowed_models:
            pytest.skip(f"Model {model} not in allowed_models configuration")

        response = proxy_client.post(
            f"{proxy_url}/v1/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": max_tokens,
                "stream": False,
            },
        )

        assert response.status_code == 200, (
            f"Expected 200 for allowed model '{model}', got {response.status_code}: {response.text}"
        )

    def test_token_usage_present(self, proxy_client, proxy_url, model, max_tokens):
        """Validate token usage in response."""
        response = proxy_client.post(
            f"{proxy_url}/v1/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": "Count to 5"}],
                "max_completion_tokens": max_tokens,
                "stream": False,
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Validate token usage
        ResponseValidator.validate_token_usage(data)

        # Check token counts are positive
        assert data["usage"]["prompt_tokens"] > 0, (
            f"prompt_tokens should be > 0 for model {model}"
        )
        assert data["usage"]["completion_tokens"] > 0, (
            f"completion_tokens should be > 0 for model {model}"
        )
        assert data["usage"]["total_tokens"] > 0, (
            f"total_tokens should be > 0 for model {model}"
        )

    def test_response_format(self, proxy_client, proxy_url, model, max_tokens):
        """Validate OpenAI response format."""
        response = proxy_client.post(
            f"{proxy_url}/v1/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": "Hi"}],
                "max_completion_tokens": max_tokens,
                "stream": False,
            },
        )

        assert response.status_code == 200
        data = response.json()

        ResponseValidator.validate_openai_format(data)

    def test_common_attributes(self, proxy_client, proxy_url, model, max_tokens):
        """Check id, object, created, model, choices."""
        response = proxy_client.post(
            f"{proxy_url}/v1/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": "Test"}],
                "max_completion_tokens": max_tokens,
                "stream": False,
            },
        )

        assert response.status_code == 200
        data = response.json()

        ResponseValidator.validate_common_attributes(data)

        # Verify model name matches
        actual_model = data["model"]
        if any(keyword in model for keyword in ["sonnet", "haiku", "opus", "claude"]):
            assert model.replace(".", "-") in actual_model.replace(".", "-"), (
                f"Invalid claude model model='{model}', got '{actual_model}'"
            )
        else:
            assert data["model"].startswith(model), (
                f"Expected model='{model}', got '{actual_model}'"
            )

    def test_multiple_messages(self, proxy_client, proxy_url, model, max_tokens):
        """Test with multiple messages in conversation."""
        response = proxy_client.post(
            f"{proxy_url}/v1/chat/completions",
            json={
                "model": model,
                "messages": [
                    {"role": "user", "content": "What is 2+2?"},
                    {"role": "assistant", "content": "4"},
                    {"role": "user", "content": "What is 3+3?"},
                ],
                "max_completion_tokens": max_tokens,
                "stream": False,
            },
        )

        assert response.status_code == 200
        data = response.json()

        ResponseValidator.validate_openai_format(data)
        ResponseValidator.validate_token_usage(data)


@pytest.mark.integration
@pytest.mark.real
class TestChatCompletionsModelFilters:
    """Integration tests for chat completions model filters."""

    def test_filtered_model_returns_not_found(
        self, proxy_client, proxy_url, max_tokens, model_filter_tests
    ):
        """Verify filtered models return 404 not_found_error."""
        if not model_filter_tests.get("enabled"):
            pytest.skip("Model filter integration tests are disabled")

        filtered_models = model_filter_tests.get("filtered_models", [])
        if not filtered_models:
            pytest.skip("No filtered models configured for integration tests")

        filtered_model = filtered_models[0]

        response = proxy_client.post(
            f"{proxy_url}/v1/chat/completions",
            json={
                "model": filtered_model,
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": max_tokens,
                "stream": False,
            },
        )

        assert response.status_code == 404, (
            f"Expected 404 for filtered model '{filtered_model}', got {response.status_code}"
        )
        data = response.json()
        assert data.get("error", {}).get("type") == "not_found_error"

    def test_include_only_filters_expose_expected_models(
        self, proxy_client, proxy_url, model_filter_tests
    ):
        """Verify include-only filters keep only expected models."""
        if not model_filter_tests.get("enabled"):
            pytest.skip("Model filter integration tests are disabled")

        include_only = model_filter_tests.get("include_only", {})
        if not include_only:
            pytest.skip("Include-only filter scenario not configured")

        response = proxy_client.get(f"{proxy_url}/v1/models")
        assert response.status_code == 200
        model_ids = [model["id"] for model in response.json().get("data", [])]

        expected_models = include_only.get("expected_models", [])
        filtered_models = include_only.get("filtered_models", [])

        for expected_model in expected_models:
            assert expected_model in model_ids, (
                f"Expected model '{expected_model}' missing from /v1/models"
            )

        for filtered_model in filtered_models:
            assert filtered_model not in model_ids, (
                f"Filtered model '{filtered_model}' was listed in /v1/models"
            )

    def test_exclude_only_filters_hide_expected_models(
        self, proxy_client, proxy_url, model_filter_tests
    ):
        """Verify exclude-only filters hide configured models."""
        if not model_filter_tests.get("enabled"):
            pytest.skip("Model filter integration tests are disabled")

        exclude_only = model_filter_tests.get("exclude_only", {})
        if not exclude_only:
            pytest.skip("Exclude-only filter scenario not configured")

        response = proxy_client.get(f"{proxy_url}/v1/models")
        assert response.status_code == 200
        model_ids = [model["id"] for model in response.json().get("data", [])]

        expected_models = exclude_only.get("expected_models", [])
        filtered_models = exclude_only.get("filtered_models", [])

        for expected_model in expected_models:
            assert expected_model in model_ids, (
                f"Expected model '{expected_model}' missing from /v1/models"
            )

        for filtered_model in filtered_models:
            assert filtered_model not in model_ids, (
                f"Filtered model '{filtered_model}' was listed in /v1/models"
            )

    def test_combined_filters_expose_expected_models(
        self, proxy_client, proxy_url, model_filter_tests
    ):
        """Verify combined include+exclude filters apply precedence correctly."""
        if not model_filter_tests.get("enabled"):
            pytest.skip("Model filter integration tests are disabled")

        combined = model_filter_tests.get("combined", {})
        if not combined:
            pytest.skip("Combined filter scenario not configured")

        response = proxy_client.get(f"{proxy_url}/v1/models")
        assert response.status_code == 200
        model_ids = [model["id"] for model in response.json().get("data", [])]

        expected_models = combined.get("expected_models", [])
        filtered_models = combined.get("filtered_models", [])

        for expected_model in expected_models:
            assert expected_model in model_ids, (
                f"Expected model '{expected_model}' missing from /v1/models"
            )

        for filtered_model in filtered_models:
            assert filtered_model not in model_ids, (
                f"Filtered model '{filtered_model}' was listed in /v1/models"
            )


@pytest.mark.integration
@pytest.mark.real
@pytest.mark.streaming
@pytest.mark.parametrize(
    "model",
    [
        "anthropic--claude-4.5-sonnet",
        "sonnet-4.5",
        "gpt-4.1",
        "gpt-5",
        "gemini-2.5-pro",
    ],
)
class TestChatCompletionsStreaming:
    """Tests for streaming chat completions."""

    def test_streaming_completion(self, proxy_client, proxy_url, model, max_tokens):
        """Test basic streaming response."""
        # Use specific request format for different models
        if model == "gpt-5":
            request_data = {
                "model": model,
                "messages": [{"role": "user", "content": "Hi"}],
                "max_completion_tokens": max_tokens,
                "reasoning_effort": "low",
                "stream": False,
            }
            use_streaming = True
        elif model == "sonnet-4.5":
            request_data = {
                "model": model,
                "messages": [{"role": "user", "content": "Hi"}],
                "max_completion_tokens": max_tokens,
                "stream": True,  # Required for sonnet-4.5
            }
            use_streaming = True
        else:
            request_data = {
                "model": model,
                "messages": [{"role": "user", "content": "Hi"}],
                "max_completion_tokens": max_tokens,
                "stream": True,
            }
            use_streaming = True

        response = proxy_client.post(
            f"{proxy_url}/v1/chat/completions",
            json=request_data,
            stream=use_streaming,
        )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        chunks = []
        for line in response.iter_lines():
            if line:
                chunks.append(line)

        assert len(chunks) > 0, f"No streaming chunks received for model {model}"

    def test_sse_format(self, proxy_client, proxy_url, model, max_tokens):
        """Validate SSE message format."""
        response: requests.Response = proxy_client.post(
            f"{proxy_url}/v1/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": max_tokens,
                "stream": True,
            },
            stream=True,
        )

        ResponseValidator.validate_sse_response(model, response)

    def test_streaming_chunks_format(self, proxy_client, proxy_url, model, max_tokens):
        """Validate chunk structure."""
        if model == "gpt-5":
            request_body_json = {
                "model": model,
                "messages": [{"role": "user", "content": "Say hello"}],
                "reasoning_effort": "low",
                "max_completion_tokens": 1024,
                "stream": True,
            }
        else:
            request_body_json = {
                "model": model,
                "messages": [{"role": "user", "content": "Say hello"}],
                "max_tokens": max_tokens,
                "stream": True,
            }

        response: requests.Response = proxy_client.post(
            f"{proxy_url}/v1/chat/completions",
            json=request_body_json,
            stream=True,
        )

        # TODO: Gemini-2.5-pro's wire format is different and not yet supported
        # data: {
        #   candidates: [
        #     {
        #       content: {
        #         parts: [
        #           {
        #             text: ...
        #           }
        #         ],
        #         role: model
        #       },
        #       finishReason: MAX_TOKENS,
        #       index: 0
        #     }
        #   ],
        #   usageMetadata: {
        #     promptTokenCount: 50,
        #     candidatesTokenCount: 1024,
        #     totalTokenCount: 1074
        #   }
        # }
        event_chunk_count, event_chunk_list, data_chunk_count, data_chunk_list = (
            ResponseValidator.validate_sse_response(model, response)
        )

        parsed_chunks = []

        for data_str in data_chunk_list:
            data_str = data_str[6:]
            if data_str != "[DONE]":
                chunk_data = json.loads(data_str)
                parsed_chunks.append(chunk_data)

        assert len(parsed_chunks) > 0, (
            f"No valid chunks parsed for model {model}, got {data_chunk_list} and {event_chunk_list}"
        )

        # Extract content
        content = ResponseValidator.extract_streaming_content(parsed_chunks)
        assert len(content) > 0, (
            f"No content extracted from streaming chunks for model {model}, got {parsed_chunks}, {data_chunk_list} and {event_chunk_list}"
        )

    def test_streaming_token_usage(self, proxy_client, proxy_url, model, max_tokens):
        """Check token usage in final chunk.

        Note: OpenAI models (gpt-4.1, gpt-5) do not include token usage in streaming responses.
        This is an OpenAI API limitation. Token usage is available in non-streaming responses.
        Only Claude and Gemini models include usage in streaming.
        """
        # Skip this test for OpenAI models since they don't provide usage in streaming
        if any(keyword in model for keyword in ["gpt-", "gpt4"]):
            pytest.skip(
                f"OpenAI model {model} does not include token usage in streaming responses (API limitation)"
            )

        response = proxy_client.post(
            f"{proxy_url}/v1/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": "Count to 3"}],
                "max_tokens": max_tokens,
                "stream": True,
            },
            stream=True,
        )

        assert response.status_code == 200

        parsed_chunks = []

        for line in response.iter_lines():
            if line:
                data_str = line[6:].decode("utf-8").strip()
                if data_str != "[DONE]":
                    chunk_data = json.loads(data_str)
                    parsed_chunks.append(chunk_data)

        # Get final chunk with usage
        final_chunk = ResponseValidator.get_final_chunk_with_usage(parsed_chunks)
        assert final_chunk is not None, (
            f"No chunk with usage information found for model {model}"
        )

        # Validate token usage
        ResponseValidator.validate_token_usage(final_chunk)

    def test_done_signal(self, proxy_client, proxy_url, model, max_tokens):
        """Verify [DONE] signal at end of stream."""
        response = proxy_client.post(
            f"{proxy_url}/v1/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": "Hi"}],
                "max_tokens": max_tokens,
                "stream": True,
            },
            stream=True,
        )

        assert response.status_code == 200

        found_done = False
        for line in response.iter_lines():
            if line:
                data_str = line[6:].decode("utf-8").strip()
                if data_str == "[DONE]":
                    found_done = True
                    break

        assert found_done, f"[DONE] signal not found in stream for model {model}"

    def test_single_done_signal(self, proxy_client, proxy_url, model, max_tokens):
        """Verify exactly ONE [DONE] signal at end of stream (no duplicates)."""
        response = proxy_client.post(
            f"{proxy_url}/v1/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": "Say hello"}],
                "max_tokens": max_tokens,
                "stream": True,
            },
            stream=True,
        )

        assert response.status_code == 200

        done_count = 0
        all_lines = []
        for line in response.iter_lines():
            if line:
                line_str = line.decode("utf-8")
                all_lines.append(line_str)
                data_str = (
                    line_str[6:].strip()
                    if line_str.startswith("data: ")
                    else line_str.strip()
                )
                if data_str == "[DONE]":
                    done_count += 1

        assert done_count == 1, (
            f"Expected exactly 1 [DONE] signal for model {model}, but found {done_count}. "
            f"Lines: {all_lines[-5:]}"  # Show last 5 lines for debugging
        )


@pytest.mark.integration
@pytest.mark.real
@pytest.mark.smoke
@pytest.mark.parametrize(
    "model,prompt",
    [
        ("anthropic--claude-4.5-sonnet", "Hello"),
        ("sonnet-4.5", "What is 2+2?"),
        ("gpt-4.1", "Tell me a joke"),
        ("gpt-5", "Explain Python"),
        ("gemini-2.5-pro", "How are you?"),
    ],
)
class TestChatCompletionsSmoke:
    """Quick smoke tests for each model."""

    def test_simple_prompt_smoke(
        self, proxy_client, proxy_url, model, prompt, max_tokens
    ):
        """Quick smoke test with simple prompt."""
        # Use specific request format for different models
        if model == "gpt-5":
            request_data = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "reasoning_effort": "low",
            }
            use_streaming = False
        elif model == "sonnet-4.5":
            request_data = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "stream": False,  # Required for sonnet-4.5
            }
            use_streaming = False
        else:
            request_data = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "stream": False,
            }
            use_streaming = False

        response = proxy_client.post(
            f"{proxy_url}/v1/chat/completions",
            json=request_data,
            stream=use_streaming,
        )

        assert response.status_code == 200, (
            f"Smoke test failed for {model}: {response.text}"
        )

        # Handle non-streaming response
        data = response.json()
        assert "choices" in data
        assert len(data["choices"]) > 0
        assert data["choices"][0]["message"]["content"]

    def test_streaming_smoke(self, proxy_client, proxy_url, model, prompt, max_tokens):
        """Quick smoke test for streaming."""
        # Use specific request format for different models
        if model == "gpt-5":
            request_data = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_completion_tokens": 1000,
                "stream": False,
                "reasoning_effort": "low",
            }
            use_streaming = False
        elif model == "sonnet-4.5":
            request_data = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "stream": True,  # Required for sonnet-4.5
            }
            use_streaming = True
        else:
            request_data = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "stream": True,
            }
            use_streaming = True

        response = proxy_client.post(
            f"{proxy_url}/v1/chat/completions",
            json=request_data,
            stream=use_streaming,
        )

        assert response.status_code == 200, f"Streaming smoke test failed for {model}"

        chunk_count = 0
        for line in response.iter_lines():
            if line:
                chunk_count += 1

        assert chunk_count > 0, f"No streaming chunks for {model}"
