"""
Test suite for proxy_helpers.py module.

Tests the Detector and Converters classes that handle model detection
and payload conversion between different AI provider formats.
"""

import json
import pytest
from unittest.mock import patch
import proxy_helpers
from proxy_helpers import Detector, Converters


class TestDetector:
    """Test cases for the Detector class."""

    def test_is_claude_model_with_claude_keyword(self):
        """Test detection of Claude models with 'claude' keyword."""
        assert Detector.is_claude_model("claude-3.5-sonnet") is True
        assert Detector.is_claude_model("claude-4") is True
        assert Detector.is_claude_model("anthropic--claude-3-sonnet") is True

    def test_is_claude_model_with_sonnet_keyword(self):
        """Test detection of Claude models with 'sonnet' keyword."""
        assert Detector.is_claude_model("sonnet-3.5") is True
        assert Detector.is_claude_model("SONNET") is True
        assert Detector.is_claude_model("sonne") is True

    def test_is_claude_model_with_haiku_keyword(self):
        """Test detection of Claude models with 'haiku' keyword."""
        assert Detector.is_claude_model("claude-3-haiku") is True
        assert Detector.is_claude_model("haiku-model") is True

    def test_is_claude_model_with_partial_matches(self):
        """Test detection with partial keyword matches."""
        assert Detector.is_claude_model("clau") is True
        assert Detector.is_claude_model("claud") is True
        assert Detector.is_claude_model("sonn") is True

    def test_is_claude_model_negative_cases(self):
        """Test that non-Claude models are not detected."""
        assert Detector.is_claude_model("gpt-4") is False
        assert Detector.is_claude_model("gemini-pro") is False
        assert Detector.is_claude_model("llama-2") is False
        assert Detector.is_claude_model("") is False

    def test_is_claude_37_or_4_with_version_37(self):
        """Test detection of Claude 3.7 models."""
        assert Detector.is_claude_37_or_4("claude-3.7-sonnet") is True
        assert Detector.is_claude_37_or_4("anthropic--claude-3.7") is True

    def test_is_claude_37_or_4_with_version_4(self):
        """Test detection of Claude 4.x models."""
        assert Detector.is_claude_37_or_4("claude-4-sonnet") is True
        assert Detector.is_claude_37_or_4("claude-4.0") is True
        assert Detector.is_claude_37_or_4("claude-4.5-opus") is True

    def test_is_claude_37_or_4_excludes_35(self):
        """Test that Claude 3.5 models are excluded."""
        assert Detector.is_claude_37_or_4("claude-3.5-sonnet") is False

    def test_is_claude_37_or_4_without_35_in_name(self):
        """Test models without 3.5 in name are detected as 3.7/4."""
        assert Detector.is_claude_37_or_4("claude-sonnet") is True
        assert Detector.is_claude_37_or_4("claude-opus") is True

    def test_is_gemini_model_with_gemini_keyword(self):
        """Test detection of Gemini models."""
        assert Detector.is_gemini_model("gemini-pro") is True
        assert Detector.is_gemini_model("gemini-1.5-pro") is True
        assert Detector.is_gemini_model("gemini-2.5-flash") is True
        assert Detector.is_gemini_model("GEMINI-PRO") is True

    def test_is_gemini_model_with_specific_versions(self):
        """Test detection of specific Gemini versions."""
        assert Detector.is_gemini_model("gemini-1.5-pro-latest") is True
        assert Detector.is_gemini_model("gemini-2.5-flash-preview") is True
        assert Detector.is_gemini_model("gemini-flash") is True

    def test_is_gemini_model_negative_cases(self):
        """Test that non-Gemini models are not detected."""
        assert Detector.is_gemini_model("gpt-4") is False
        assert Detector.is_gemini_model("claude-3.5-sonnet") is False
        assert Detector.is_gemini_model("llama-2") is False
        assert Detector.is_gemini_model("") is False


class TestConvertersUtility:
    """Test utility methods in Converters class."""

    def test_str_to_int_valid_string(self):
        """Test conversion of valid string to integer."""
        assert Converters.str_to_int("123") == 123
        assert Converters.str_to_int("0") == 0
        assert Converters.str_to_int("-456") == -456

    def test_str_to_int_invalid_string(self):
        """Test that invalid strings raise ValueError."""
        with pytest.raises(ValueError, match="Cannot convert 'abc' to int"):
            Converters.str_to_int("abc")
        
        with pytest.raises(ValueError):
            Converters.str_to_int("12.34")


class TestConvertersOpenAIToClaudeRequests:
    """Test OpenAI to Claude request conversion methods."""

    def test_convert_openai_to_claude_basic(self):
        """Test basic OpenAI to Claude conversion."""
        payload = {
            "messages": [
                {"role": "user", "content": "Hello"}
            ],
            "max_tokens": 1000,
            "temperature": 0.7
        }
        
        result = Converters.convert_openai_to_claude(payload)
        
        assert result["anthropic_version"] == "bedrock-2023-05-31"
        assert result["max_tokens"] == 1000
        assert result["temperature"] == 0.7
        assert result["system"] == ""
        assert len(result["messages"]) == 1
        assert result["messages"][0]["content"] == "Hello"

    def test_convert_openai_to_claude_with_system_message(self):
        """Test conversion with system message extraction."""
        payload = {
            "messages": [
                {"role": "system", "content": "You are a helpful assistant"},
                {"role": "user", "content": "Hello"}
            ]
        }
        
        result = Converters.convert_openai_to_claude(payload)
        
        assert result["system"] == "You are a helpful assistant"
        assert len(result["messages"]) == 1
        assert result["messages"][0]["role"] == "user"

    def test_convert_openai_to_claude_default_values(self):
        """Test that default values are applied correctly."""
        payload = {
            "messages": [{"role": "user", "content": "Test"}]
        }
        
        result = Converters.convert_openai_to_claude(payload)
        
        assert result["max_tokens"] == 4096000
        assert result["temperature"] == 1.0

    def test_convert_openai_to_claude37_basic(self):
        """Test basic OpenAI to Claude 3.7 conversion."""
        payload = {
            "messages": [
                {"role": "user", "content": "Hello"}
            ],
            "max_tokens": 2000,
            "temperature": 0.5
        }
        
        result = Converters.convert_openai_to_claude37(payload)
        
        assert "messages" in result
        assert len(result["messages"]) == 1
        assert result["messages"][0]["role"] == "user"
        assert result["messages"][0]["content"][0]["text"] == "Hello"
        assert result["inferenceConfig"]["maxTokens"] == 2000
        assert result["inferenceConfig"]["temperature"] == 0.5

    def test_convert_openai_to_claude37_with_system_message(self):
        """Test Claude 3.7 conversion with system message prepended."""
        payload = {
            "messages": [
                {"role": "system", "content": "System prompt"},
                {"role": "user", "content": "User message"}
            ]
        }
        
        result = Converters.convert_openai_to_claude37(payload)
        
        # System message should be prepended as first user message
        assert len(result["messages"]) == 2
        assert result["messages"][0]["role"] == "user"
        assert result["messages"][0]["content"][0]["text"] == "System prompt"
        assert result["messages"][1]["content"][0]["text"] == "User message"

    def test_convert_openai_to_claude37_with_stop_sequences(self):
        """Test conversion with stop sequences."""
        payload = {
            "messages": [{"role": "user", "content": "Test"}],
            "stop": ["STOP", "END"]
        }
        
        result = Converters.convert_openai_to_claude37(payload)
        
        assert result["inferenceConfig"]["stopSequences"] == ["STOP", "END"]

    def test_convert_openai_to_claude37_with_list_content(self):
        """Test conversion with list-based content."""
        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Hello"},
                        {"type": "text", "text": "World"}
                    ]
                }
            ]
        }
        
        result = Converters.convert_openai_to_claude37(payload)
        
        assert len(result["messages"][0]["content"]) == 2
        assert result["messages"][0]["content"][0]["text"] == "Hello"
        assert result["messages"][0]["content"][1]["text"] == "World"


class TestConvertersClaudeToOpenAI:
    """Test Claude to OpenAI conversion methods."""

    def test_convert_claude_request_to_openai_basic(self):
        """Test basic Claude to OpenAI request conversion."""
        payload = {
            "model": "claude-3.5-sonnet",
            "messages": [
                {"role": "user", "content": "Hello"}
            ],
            "max_tokens": 1000,
            "temperature": 0.7
        }
        
        result = Converters.convert_claude_request_to_openai(payload)
        
        assert result["model"] == "claude-3.5-sonnet"
        assert result["max_completion_tokens"] == 1000
        assert result["temperature"] == 0.7
        assert len(result["messages"]) == 1

    def test_convert_claude_request_to_openai_with_system(self):
        """Test conversion with system message."""
        payload = {
            "system": "You are helpful",
            "messages": [{"role": "user", "content": "Hi"}]
        }
        
        result = Converters.convert_claude_request_to_openai(payload)
        
        assert len(result["messages"]) == 2
        assert result["messages"][0]["role"] == "system"
        assert result["messages"][0]["content"] == "You are helpful"

    def test_convert_claude_request_to_openai_with_tools(self):
        """Test conversion with tools."""
        payload = {
            "messages": [{"role": "user", "content": "Test"}],
            "tools": [
                {
                    "name": "get_weather",
                    "description": "Get weather info",
                    "input_schema": {
                        "type": "object",
                        "properties": {"location": {"type": "string"}}
                    }
                }
            ]
        }
        
        result = Converters.convert_claude_request_to_openai(payload)
        
        assert "tools" in result
        assert len(result["tools"]) == 1
        assert result["tools"][0]["type"] == "function"
        assert result["tools"][0]["function"]["name"] == "get_weather"

    def test_convert_claude_to_openai_standard_model(self):
        """Test Claude 3.5 response to OpenAI conversion."""
        response = {
            "id": "msg_123",
            "model": "claude-3.5-sonnet",
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Hello, how can I help?"}
            ],
            "stop_reason": "end_turn",
            "usage": {
                "input_tokens": 10,
                "output_tokens": 20
            }
        }
        
        result = Converters.convert_claude_to_openai(response, "claude-3.5-sonnet")
        
        assert result["object"] == "chat.completion"
        assert result["id"] == "msg_123"
        assert result["model"] == "claude-3.5-sonnet"
        assert result["choices"][0]["message"]["content"] == "Hello, how can I help?"
        assert result["choices"][0]["finish_reason"] == "end_turn"
        assert result["usage"]["prompt_tokens"] == 10
        assert result["usage"]["completion_tokens"] == 20

    def test_convert_claude37_to_openai_basic(self):
        """Test Claude 3.7/4 response to OpenAI conversion."""
        response = {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [
                        {"text": "Response text"}
                    ]
                }
            },
            "stopReason": "end_turn",
            "usage": {
                "inputTokens": 15,
                "outputTokens": 25,
                "totalTokens": 40
            }
        }
        
        result = Converters.convert_claude37_to_openai(response, "claude-3.7-sonnet")
        
        assert result["object"] == "chat.completion"
        assert result["model"] == "claude-3.7-sonnet"
        assert result["choices"][0]["message"]["content"] == "Response text"
        assert result["choices"][0]["finish_reason"] == "stop"
        assert result["usage"]["prompt_tokens"] == 15
        assert result["usage"]["completion_tokens"] == 25

    def test_convert_claude37_to_openai_with_cache_tokens(self):
        """Test conversion with cache token details."""
        response = {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [{"text": "Cached response"}]
                }
            },
            "stopReason": "end_turn",
            "usage": {
                "inputTokens": 100,
                "outputTokens": 50,
                "totalTokens": 150,
                "cacheReadInputTokens": 80,
                "cacheCreationInputTokens": 20
            }
        }
        
        result = Converters.convert_claude37_to_openai(response)
        
        assert "prompt_tokens_details" in result["usage"]
        assert result["usage"]["prompt_tokens_details"]["cached_tokens"] == 80
        assert result["usage"]["prompt_tokens_details"]["cache_creation_tokens"] == 20


class TestConvertersGemini:
    """Test Gemini conversion methods."""

    def test_convert_openai_to_gemini_single_message(self):
        """Test OpenAI to Gemini conversion with single message."""
        payload = {
            "messages": [
                {"role": "user", "content": "Hello Gemini"}
            ],
            "max_tokens": 1000,
            "temperature": 0.8
        }
        
        result = Converters.convert_openai_to_gemini(payload)
        
        assert result["contents"]["role"] == "user"
        assert result["contents"]["parts"]["text"] == "Hello Gemini"
        assert result["generation_config"]["maxOutputTokens"] == 1000
        assert result["generation_config"]["temperature"] == 0.8
        assert "safety_settings" in result

    def test_convert_openai_to_gemini_with_system_message(self):
        """Test conversion with system message prepended."""
        payload = {
            "messages": [
                {"role": "system", "content": "System instruction"},
                {"role": "user", "content": "User query"}
            ]
        }
        
        result = Converters.convert_openai_to_gemini(payload)
        
        # System message should be prepended to user content
        assert "System instruction" in result["contents"]["parts"]["text"]
        assert "User query" in result["contents"]["parts"]["text"]

    def test_convert_openai_to_gemini_multiple_messages(self):
        """Test conversion with multiple messages."""
        payload = {
            "messages": [
                {"role": "user", "content": "First message"},
                {"role": "assistant", "content": "First response"},
                {"role": "user", "content": "Second message"}
            ]
        }
        
        result = Converters.convert_openai_to_gemini(payload)
        
        assert isinstance(result["contents"], list)
        assert len(result["contents"]) == 3
        assert result["contents"][0]["role"] == "user"
        assert result["contents"][1]["role"] == "model"
        assert result["contents"][2]["role"] == "user"

    def test_convert_gemini_to_openai_basic(self):
        """Test Gemini to OpenAI response conversion."""
        response = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "Gemini response"}]
                    },
                    "finishReason": "STOP"
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 10,
                "candidatesTokenCount": 15,
                "totalTokenCount": 25
            }
        }
        
        result = Converters.convert_gemini_to_openai(response, "gemini-pro")
        
        assert result["object"] == "chat.completion"
        assert result["model"] == "gemini-pro"
        assert result["choices"][0]["message"]["content"] == "Gemini response"
        assert result["choices"][0]["finish_reason"] == "stop"
        assert result["usage"]["prompt_tokens"] == 10
        assert result["usage"]["completion_tokens"] == 15

    def test_convert_gemini_to_openai_finish_reasons(self):
        """Test finish reason mapping."""
        test_cases = [
            ("STOP", "stop"),
            ("MAX_TOKENS", "length"),
            ("SAFETY", "content_filter"),
            ("RECITATION", "content_filter"),
            ("OTHER", "stop")
        ]
        
        for gemini_reason, expected_openai_reason in test_cases:
            response = {
                "candidates": [
                    {
                        "content": {"parts": [{"text": "Test"}]},
                        "finishReason": gemini_reason
                    }
                ],
                "usageMetadata": {}
            }
            
            result = Converters.convert_gemini_to_openai(response)
            assert result["choices"][0]["finish_reason"] == expected_openai_reason

    def test_convert_gemini_response_to_claude(self):
        """Test Gemini to Claude response conversion."""
        response = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "Gemini to Claude"}]
                    },
                    "finishReason": "STOP"
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 20,
                "candidatesTokenCount": 30
            }
        }
        
        result = Converters.convert_gemini_response_to_claude(response, "gemini-pro")
        
        assert result["type"] == "message"
        assert result["role"] == "assistant"
        assert result["model"] == "gemini-pro"
        assert result["content"][0]["type"] == "text"
        assert result["content"][0]["text"] == "Gemini to Claude"
        assert result["stop_reason"] == "end_turn"
        assert result["usage"]["input_tokens"] == 20
        assert result["usage"]["output_tokens"] == 30


class TestConvertersClaudeToGemini:
    """Test Claude to Gemini conversion methods."""

    def test_convert_claude_request_to_gemini_basic(self):
        """Test basic Claude to Gemini request conversion."""
        payload = {
            "messages": [
                {"role": "user", "content": "Hello"}
            ],
            "max_tokens": 500,
            "temperature": 0.9
        }
        
        result = Converters.convert_claude_request_to_gemini(payload)
        
        assert isinstance(result["contents"], list)
        assert result["contents"][0]["role"] == "user"
        assert result["generation_config"]["maxOutputTokens"] == 500
        assert result["generation_config"]["temperature"] == 0.9

    def test_convert_claude_request_to_gemini_with_system(self):
        """Test conversion with system prompt."""
        payload = {
            "system": "System instruction",
            "messages": [
                {"role": "user", "content": "User message"}
            ]
        }
        
        result = Converters.convert_claude_request_to_gemini(payload)
        
        # System should be prepended to first user message
        first_content = result["contents"][0]["parts"]["text"]
        assert "System instruction" in first_content
        assert "User message" in first_content


class TestConvertersOpenAIToClaude:
    """Test OpenAI to Claude response conversion."""

    def test_convert_openai_response_to_claude_basic(self):
        """Test basic OpenAI to Claude response conversion."""
        response = {
            "id": "chatcmpl-123",
            "model": "gpt-4",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "OpenAI response"
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20
            }
        }
        
        result = Converters.convert_openai_response_to_claude(response)
        
        assert result["type"] == "message"
        assert result["role"] == "assistant"
        assert result["model"] == "gpt-4"
        assert result["content"][0]["type"] == "text"
        assert result["content"][0]["text"] == "OpenAI response"
        assert result["stop_reason"] == "end_turn"

    def test_convert_openai_response_to_claude_with_tools(self):
        """Test conversion with tool calls."""
        response = {
            "id": "chatcmpl-456",
            "model": "gpt-4",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Using tool",
                        "tool_calls": [
                            {
                                "id": "call_123",
                                "type": "function",
                                "function": {
                                    "name": "get_weather",
                                    "arguments": '{"location": "NYC"}'
                                }
                            }
                        ]
                    },
                    "finish_reason": "tool_calls"
                }
            ],
            "usage": {"prompt_tokens": 15, "completion_tokens": 25}
        }
        
        result = Converters.convert_openai_response_to_claude(response)
        
        assert len(result["content"]) == 2
        assert result["content"][0]["type"] == "text"
        assert result["content"][1]["type"] == "tool_use"
        assert result["content"][1]["name"] == "get_weather"
        assert result["stop_reason"] == "tool_use"


class TestConvertersStreamingChunks:
    """Test streaming chunk conversion methods."""

    def test_convert_gemini_chunk_to_claude_delta(self):
        """Test Gemini chunk to Claude delta conversion."""
        chunk = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "chunk text"}]
                    }
                }
            ]
        }
        
        result = Converters.convert_gemini_chunk_to_claude_delta(chunk)
        
        assert result is not None
        assert result["type"] == "content_block_delta"
        assert result["delta"]["type"] == "text_delta"
        assert result["delta"]["text"] == "chunk text"

    def test_convert_openai_chunk_to_claude_delta(self):
        """Test OpenAI chunk to Claude delta conversion."""
        chunk = {
            "choices": [
                {
                    "delta": {"content": "delta content"}
                }
            ]
        }
        
        result = Converters.convert_openai_chunk_to_claude_delta(chunk)
        
        assert result is not None
        assert result["type"] == "content_block_delta"
        assert result["delta"]["text"] == "delta content"

    def test_convert_gemini_chunk_to_openai_basic(self):
        """Test Gemini chunk to OpenAI SSE conversion."""
        chunk = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "streaming text"}]
                    }
                }
            ]
        }
        
        result = Converters.convert_gemini_chunk_to_openai(chunk, "gemini-pro")
        
        assert result is not None
        assert result.startswith("")
        assert "streaming text" in result
        assert "chat.completion.chunk" in result

    def test_convert_gemini_chunk_to_openai_with_finish(self):
        """Test Gemini chunk with finish reason."""
        chunk = {
            "candidates": [
                {
                    "content": {"parts": [{"text": "final"}]},
                    "finishReason": "STOP"
                }
            ]
        }
        
        result = Converters.convert_gemini_chunk_to_openai(chunk, "gemini-pro")
        
        assert "finish_reason" in result
        assert '"finish_reason": "stop"' in result


class TestConvertersBedrockFormat:
    """Test Bedrock-specific conversion methods."""

    def test_convert_claude_request_for_bedrock_basic(self):
        """Test Claude request to Bedrock format conversion."""
        payload = {
            "model": "claude-3.5-sonnet",
            "messages": [
                {"role": "user", "content": "Test"}
            ],
            "max_tokens": 1000,
            "temperature": 0.7
        }
        
        result = Converters.convert_claude_request_for_bedrock(payload)
        
        assert result["model"] == "claude-3.5-sonnet"
        assert result["max_tokens"] == 1000
        assert result["temperature"] == 0.7
        assert result["anthropic_version"] == "bedrock-2023-05-31"

    def test_convert_claude_request_for_bedrock_removes_cache_control(self):
        """Test that cache_control fields are removed."""
        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Test",
                            "cache_control": {"type": "ephemeral"}
                        }
                    ]
                }
            ]
        }
        
        result = Converters.convert_claude_request_for_bedrock(payload)
        
        content_item = result["messages"][0]["content"][0]
        assert "cache_control" not in content_item
        assert content_item["text"] == "Test"

    def test_convert_claude_request_for_bedrock_with_tools(self):
        """Test Bedrock conversion preserves tools."""
        payload = {
            "messages": [{"role": "user", "content": "Test"}],
            "tools": [
                {
                    "name": "calculator",
                    "description": "Calculate math",
                    "input_schema": {"type": "object"}
                }
            ]
        }
        
        result = Converters.convert_claude_request_for_bedrock(payload)
        
        assert "tools" in result
        assert len(result["tools"]) == 1
        assert result["tools"][0]["name"] == "calculator"


class TestConvertersErrorHandling:
    """Test error handling in conversion methods."""

    def test_convert_claude_to_openai_invalid_response(self):
        """Test error handling for invalid Claude response."""
        invalid_response = {"invalid": "structure"}
        
        result = Converters.convert_claude_to_openai(invalid_response, "claude-3.5")
        
        assert "error" in result
        assert "Invalid response" in result["error"]

    def test_convert_gemini_to_openai_missing_candidates(self):
        """Test error handling for missing candidates."""
        invalid_response = {"usageMetadata": {}}
        
        result = Converters.convert_gemini_to_openai(invalid_response)
        
        assert result["object"] == "error"
        assert "proxy_conversion_error" in result["type"]

    def test_convert_claude37_to_openai_invalid_structure(self):
        """Test error handling for invalid Claude 3.7 response."""
        invalid_response = {"output": "not a dict"}
        
        result = Converters.convert_claude37_to_openai(invalid_response)
        
        assert result["object"] == "error"
        assert "Failed to convert" in result["message"]

    def test_convert_openai_response_to_claude_missing_choices(self):
        """Test error handling for missing choices."""
        invalid_response = {"id": "test", "model": "gpt-4"}
        
        result = Converters.convert_openai_response_to_claude(invalid_response)
        
        assert result["type"] == "error"
        assert "proxy_conversion_error" in result["error"]["type"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])