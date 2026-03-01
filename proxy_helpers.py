import json
import os
import re
from logging import Logger
import random
import time

from converters.mappings import API_VERSION_BEDROCK_2023_05_31, STOP_REASON_MAP
from converters import chunks as chunk_converters
from converters import claude as claude_converters
from converters import gemini as gemini_converters
from converters import openai as openai_converters
from utils.logging_utils import get_server_logger

logger: Logger = get_server_logger(__name__)


def load_model_aliases():
    """Load model aliases from config/aliases.json."""
    try:
        alias_file = os.path.join(os.path.dirname(__file__), "config", "aliases.json")
        if os.path.exists(alias_file):
            with open(alias_file, "r") as f:
                logger.info(f"Loading model aliases from {alias_file}")
                return json.load(f)
        else:
            logger.warning(
                f"Alias file not found at {alias_file}, using empty defaults."
            )
            return {}
    except Exception as e:
        logger.error(f"Failed to load model aliases: {e}")
        return {}


# Model Aliases Configuration
MODEL_ALIASES = load_model_aliases()


class Detector:
    @staticmethod
    def is_claude_37_or_4(model: str):
        """
        Check if the Claude model uses Converse API format (True) or InvokeModel format (False).

        Determines API endpoint and response parsing:
        - True: Uses /converse endpoint with Converse response format
        - False: Uses /invoke endpoint with InvokeModel response format

        Args:
            model: The model name to check

        Returns:
            bool: True for models using Converse API (3.7+, 4+, non-3.5), False for InvokeModel (3.5, older)
        """
        # Check for specific version patterns to avoid false positives with dates
        # Normalize dots to hyphens to handle both "claude-4.5" and "claude-4-5" variants
        model_lower: str = model.lower().replace(".", "-")
        return (
            "claude-3-7" in model_lower
            or "claude-4" in model_lower
            or "sonnet-4" in model_lower  # Detect sonnet-4.x models
            or "haiku-4" in model_lower  # Detect haiku-4.x models
            or "opus-4" in model_lower  # Detect opus-4.x models
            or (
                "claude" in model_lower
                and not any(v in model_lower for v in ["3-5", "3-opus"])
            )
        )

    @staticmethod
    def is_claude_model(model):
        return any(
            keyword in model
            for keyword in [
                "haiku",
                "claude",
                "clau",
                "claud",
                "sonnet",
                "sonne",
                "sonn",
                "opus",
                "CLAUDE",
                "SONNET",
                "OPUS",
            ]
        )

    @staticmethod
    def is_gemini_model(model):
        """
        Check if the model is a Gemini model.

        Args:
            model: The model name to check

        Returns:
            bool: True if the model is a Gemini model, False otherwise
        """
        return any(
            keyword in model.lower()
            for keyword in [
                "gemini",
            ]
        )

    @staticmethod
    def extract_version(name):
        """
        Extract semantic version from model name using intelligent pattern matching.

        Handles:
        - Single digit versions: "4" from "gpt-4"
        - Multi-part versions: "3-5" from "claude-3-5-sonnet" or "claude-3.5-sonnet"
        - Complex names: "4" from "gpt-4-32k" (ignores context window size)
        - Timestamps: "4" from "gpt-4o-2024-05-13" (ignores date suffix)
        - Date formats: "4" from "gpt-4-0613" (ignores MMDD format)

        Avoids matching:
        - Dates (year like 2024, 20240229, 0613)
        - Context window sizes (32k, 128k, etc.)
        - Long numeric suffixes

        Args:
            name: The model name to extract version from

        Returns:
            str: The extracted version (e.g., "4", "3-5", "4-5") or None
        """
        matches = list(re.finditer(r"\d+", name))

        if not matches:
            return None

        for i, match in enumerate(matches):
            num_str = match.group(0)
            num = int(num_str)

            # Skip year-like numbers (> 100)
            if num > 100:
                continue

            # Get the character after this match
            pos_after = match.end()
            char_after = (
                name[pos_after : pos_after + 1] if pos_after < len(name) else ""
            )

            # Skip if followed by 'k' or 'm' (context window suffix like 32k)
            if char_after in "km":
                continue

            # Check if followed by a separator (. or -)
            if char_after in ".-":
                # Look ahead for the next number
                next_match = matches[i + 1] if i + 1 < len(matches) else None

                if next_match and next_match.start() == pos_after + 1:
                    # Separator immediately followed by next number
                    minor_str = next_match.group(0)
                    minor = int(minor_str)

                    # Skip date-like suffixes (3+ digit numbers like 0613, 2024, etc.)
                    if len(minor_str) >= 3:
                        return str(num)

                    # Skip if minor is 4-digit (like 2024)
                    if minor >= 1000:
                        return str(num)

                    # Check if minor is a context window (32, 128, 256, etc.)
                    context_windows = {
                        8,
                        16,
                        32,
                        64,
                        128,
                        256,
                        512,
                        1024,
                        2048,
                        4096,
                        8192,
                        32768,
                    }
                    pos_after_minor = next_match.end()
                    char_after_minor = (
                        name[pos_after_minor : pos_after_minor + 1]
                        if pos_after_minor < len(name)
                        else ""
                    )

                    if char_after_minor in "km" and minor in context_windows:
                        # This is a context window (e.g., "4-32k"), return major version only
                        return str(num)

                    # Normal multi-part version (e.g., "3-5" or "3.5")
                    return f"{num}-{minor}"

            # Single digit version with no separator following
            if char_after == "" or not char_after.isdigit():
                return str(num)

        # Fallback: return the first small non-date number
        for match in matches:
            num_str = match.group(0)
            num = int(num_str)
            if num < 100 and len(num_str) < 3:
                return str(num)

        return None

    @staticmethod
    def validate_model_mapping(configured_model: str, backend_model: str | None):
        """
        Validate that the configured model name matches the actual backend model.

        Checks for:
        1. Family mismatch (e.g. gpt vs claude)
        2. Version mismatch (e.g. 4 vs 3.5, 3.5 vs 3)
        3. Variant mismatch (e.g. sonnet vs haiku)

        Args:
            configured_model: The model alias configured in config.json
            backend_model: The actual model name from SAP AI Core

        Returns:
            tuple[bool, str | None]: (is_valid, failure_reason)
        """
        if not configured_model or not backend_model:
            return True, None  # Cannot validate if missing info

        c_norm = configured_model.lower().replace(".", "-")
        b_norm = backend_model.lower().replace(".", "-")

        # 1. Family Check
        families = ["claude", "gpt", "gemini", "text-embedding"]
        c_family = next((f for f in families if f in c_norm), None)
        b_family = next((f for f in families if f in b_norm), None)

        if c_family and b_family and c_family != b_family:
            return (
                False,
                f"Family mismatch: configured '{c_family}' but backend is '{b_family}'",
            )

        # 2. Version Check using robust regex extraction
        c_version = Detector.extract_version(c_norm)
        b_version = Detector.extract_version(b_norm)

        if c_version and b_version and c_version != b_version:
            # Allow prefix matching ONLY if the more specific version starts with the generic one
            # Examples:
            #   "4" -> "4-0613" is OK (configured is generic, backend is date-specific)
            #   "3-5" -> "3" is NOT OK (trying to match 3.5 model with 3.0)
            #   "3" -> "3-5" is NOT OK (vice versa)
            # The rule: only allow if backend is more specific (has more parts)
            c_parts = c_version.split("-")
            b_parts = b_version.split("-")

            # Allow match only if:
            # 1. They are identical, OR
            # 2. Backend is more specific AND shares the same major parts
            if len(b_parts) > len(c_parts):
                # Backend is more specific, check if it starts with configured version
                if b_version.startswith(c_version + "-"):
                    pass  # Allow this match
                else:
                    return (
                        False,
                        f"Version mismatch: configured '{c_version}' but backend is '{b_version}'",
                    )
            elif len(c_parts) > len(b_parts):
                # Configured is more specific than backend, not allowed
                return (
                    False,
                    f"Version mismatch: configured '{c_version}' but backend is '{b_version}'",
                )
            else:
                # Same number of parts but different values
                return (
                    False,
                    f"Version mismatch: configured '{c_version}' but backend is '{b_version}'",
                )

        # 3. Variant Check
        variants = ["sonnet", "haiku", "opus", "pro", "flash", "turbo", "omni"]
        c_variant = next((v for v in variants if v in c_norm), None)
        b_variant = next((v for v in variants if v in b_norm), None)

        if c_variant and b_variant and c_variant != b_variant:
            return (
                False,
                f"Variant mismatch: configured '{c_variant}' but backend is '{b_variant}'",
            )

        return True, None


class Converters:
    @staticmethod
    def str_to_int(s: str) -> int:
        """Convert a string to an integer."""
        try:
            return int(s)
        except ValueError:
            raise ValueError(f"Cannot convert '{s}' to int.")

    @staticmethod
    def convert_openai_to_claude(payload):
        return claude_converters.from_openai(payload)

    @staticmethod
    def convert_openai_to_claude37(payload):
        return claude_converters.claude_converse_from_openai(payload)

    @staticmethod
    def convert_claude_request_to_openai(payload):
        """Converts a Claude Messages API request to an OpenAI Chat Completion request."""
        logger.debug(
            f"Original Claude payload for OpenAI conversion: {json.dumps(payload, indent=2)}"
        )

        openai_messages = []
        if "system" in payload and payload["system"]:
            openai_messages.append({"role": "system", "content": payload["system"]})

        openai_messages.extend(payload.get("messages", []))

        openai_payload = {
            "model": payload.get("model"),
            "messages": openai_messages,
        }

        if "max_tokens" in payload:
            openai_payload["max_completion_tokens"] = payload["max_tokens"]
        if "temperature" in payload:
            openai_payload["temperature"] = payload["temperature"]
        if "stream" in payload:
            openai_payload["stream"] = payload["stream"]
        if "reasoning_effort" in payload:
            openai_payload["reasoning_effort"] = payload["reasoning_effort"]
        if "tools" in payload and payload["tools"]:
            # Convert Claude tools format to OpenAI tools format
            openai_tools = []
            for tool in payload["tools"]:
                openai_tool = {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool["description"],
                        "parameters": tool["input_schema"],
                    },
                }
                openai_tools.append(openai_tool)
            openai_payload["tools"] = openai_tools
            logger.debug(f"Converted {len(openai_tools)} tools for OpenAI format")

        logger.debug(
            f"Converted OpenAI payload: {json.dumps(openai_payload, indent=2)}"
        )
        return openai_payload

    @staticmethod
    def convert_claude_request_to_gemini(payload):
        return gemini_converters.from_claude(payload)

    @staticmethod
    def convert_claude_request_for_bedrock(payload):
        return claude_converters.claude_bedrock_from_claude(payload)

    @staticmethod
    def convert_claude_to_openai(response, model):
        return openai_converters.from_claude(response, model)

    @staticmethod
    def convert_claude37_to_openai(response, model_name="claude-3.7"):
        return openai_converters.from_claude37(response, model_name)

    @staticmethod
    def convert_claude_chunk_to_openai(chunk, model):
        return chunk_converters.claude_to_openai_chunk(chunk, model)

    @staticmethod
    def convert_claude37_chunk_to_openai(claude_chunk, model_name, stream_id=None):
        return chunk_converters.claude37_to_openai_chunk(
            claude_chunk, model_name, stream_id
        )

    @staticmethod
    def convert_openai_to_gemini(payload):
        return gemini_converters.from_openai(payload)

    @staticmethod
    def convert_gemini_to_openai(response, model_name="gemini-pro"):
        return openai_converters.from_gemini(response, model_name)

    @staticmethod
    def convert_gemini_response_to_claude(response, model_name="gemini-pro"):
        """
        Converts a Gemini generateContent API response payload (non-streaming)
        to the format expected by the Anthropic Claude Messages API.
        """
        try:
            logger.debug(
                f"Raw response from Gemini API for Claude conversion: {json.dumps(response, indent=2)}"
            )

            if (
                not isinstance(response, dict)
                or "candidates" not in response
                or not response["candidates"]
            ):
                raise ValueError(
                    "Invalid Gemini response: 'candidates' field is missing or empty"
                )

            first_candidate = response["candidates"][0]
            content_parts = first_candidate.get("content", {}).get("parts", [])
            if not content_parts or "text" not in content_parts[0]:
                raise ValueError(
                    "Invalid Gemini response: text content not found in 'parts'"
                )

            content_text = content_parts[0]["text"]

            # Map Gemini finishReason to Claude stop_reason
            gemini_finish_reason = first_candidate.get("finishReason", "STOP")
            claude_stop_reason = STOP_REASON_MAP["gemini_to_claude"].get(
                gemini_finish_reason, "stop_sequence"
            )

            # Extract usage
            usage_metadata = response.get("usageMetadata", {})
            prompt_tokens = usage_metadata.get("promptTokenCount", 0)
            completion_tokens = usage_metadata.get("candidatesTokenCount", 0)

            claude_response = {
                "id": f"msg_gemini_{random.randint(10000000, 99999999)}",
                "type": "message",
                "role": "assistant",
                "model": model_name,
                "content": [{"type": "text", "text": content_text}],
                "stop_reason": claude_stop_reason,
                "usage": {
                    "input_tokens": prompt_tokens,
                    "output_tokens": completion_tokens,
                },
            }
            logger.debug(
                f"Converted Gemini response to Claude format: {json.dumps(claude_response, indent=2)}"
            )
            return claude_response

        except Exception as e:
            logger.error(
                f"Error converting Gemini response to Claude format: {e}", exc_info=True
            )
            return {
                "type": "error",
                "error": {
                    "type": "proxy_conversion_error",
                    "message": f"Failed to convert Gemini response to Claude format: {str(e)}",
                },
            }

    @staticmethod
    def convert_openai_response_to_claude(response):
        """
        Converts an OpenAI Chat Completion API response payload (non-streaming)
        to the format expected by the Anthropic Claude Messages API.
        """
        try:
            logger.debug(
                f"Raw response from OpenAI API for Claude conversion: {json.dumps(response, indent=2)}"
            )

            if (
                not isinstance(response, dict)
                or "choices" not in response
                or not response["choices"]
            ):
                raise ValueError(
                    "Invalid OpenAI response: 'choices' field is missing or empty"
                )

            first_choice = response["choices"][0]
            message = first_choice.get("message", {})
            content_text = message.get("content")
            tool_calls = message.get("tool_calls", [])

            # Handle content based on whether there are tool calls
            claude_content = []
            if content_text:
                claude_content.append({"type": "text", "text": content_text})

            # Convert OpenAI tool calls to Claude format
            if tool_calls:
                for tool_call in tool_calls:
                    if tool_call.get("type") == "function":
                        function = tool_call.get("function", {})
                        claude_tool_use = {
                            "type": "tool_use",
                            "id": tool_call.get(
                                "id",
                                f"toolu_openai_{random.randint(10000000, 99999999)}",
                            ),
                            "name": function.get("name"),
                            "input": json.loads(function.get("arguments", "{}")),
                        }
                        claude_content.append(claude_tool_use)

            if not claude_content:
                raise ValueError(
                    "Invalid OpenAI response: no content or tool calls found"
                )

            # Map OpenAI finish_reason to Claude stop_reason
            openai_finish_reason = first_choice.get("finish_reason")
            claude_stop_reason = STOP_REASON_MAP["openai_to_claude"].get(
                openai_finish_reason, "stop_sequence"
            )

            # Extract usage
            usage = response.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)

            claude_response = {
                "id": response.get(
                    "id", f"msg_openai_{random.randint(10000000, 99999999)}"
                ),
                "type": "message",
                "role": "assistant",
                "model": response.get("model", "unknown_openai_model"),
                "content": claude_content,
                "stop_reason": claude_stop_reason,
                "usage": {
                    "input_tokens": prompt_tokens,
                    "output_tokens": completion_tokens,
                },
            }
            logger.debug(
                f"Converted OpenAI response to Claude format: {json.dumps(claude_response, indent=2)}"
            )
            return claude_response

        except Exception as e:
            logger.error(
                f"Error converting OpenAI response to Claude format: {e}", exc_info=True
            )
            return {
                "type": "error",
                "error": {
                    "type": "proxy_conversion_error",
                    "message": f"Failed to convert OpenAI response to Claude format: {str(e)}",
                },
            }

    @staticmethod
    def convert_gemini_chunk_to_claude_delta(gemini_chunk):
        """Extracts a Claude-formatted content delta from a Gemini streaming chunk."""
        text_delta = (
            gemini_chunk.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text")
        )
        if text_delta:
            return {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": text_delta},
            }
        return None

    @staticmethod
    def convert_openai_chunk_to_claude_delta(openai_chunk):
        """Extracts a Claude-formatted content delta from an OpenAI streaming chunk."""
        text_delta = (
            openai_chunk.get("choices", [{}])[0].get("delta", {}).get("content")
        )
        if text_delta:
            return {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": text_delta},
            }
        return None

    @staticmethod
    def convert_gemini_chunk_to_openai(gemini_chunk, model_name):
        return chunk_converters.gemini_to_openai_chunk(gemini_chunk, model_name)
