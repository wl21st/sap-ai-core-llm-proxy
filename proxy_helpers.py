import json
from logging import Logger
import random
import time

from utils.logging_utils import get_server_logger

logger: Logger = get_server_logger(__name__)


class Detector:
    @staticmethod
    def is_claude_37_or_4(model):
        """
        Check if the model is Claude 3.7 or Claude 4.

        Args:
            model: The model name to check

        Returns:
            bool: True if the model is Claude 3.7 or Claude 4, False otherwise
        """
        return (
            any(version in model for version in ["3.7", "4", "4.5"])
            or "3.5" not in model
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
                "CLAUDE",
                "SONNET",
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
        # Extract system message if present
        system_message = ""
        messages = payload["messages"]
        if messages and messages[0]["role"] == "system":
            system_message = messages.pop(0)["content"]
        # Conversion logic from OpenAI to Claude API format
        claude_payload = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": payload.get("max_tokens", 4096000),
            "temperature": payload.get("temperature", 1.0),
            "system": system_message,
            "messages": messages,
            # "thinking": {
            #     "type": "enabled",
            #     "budget_tokens": 16000
            # },
        }
        return claude_payload

    @staticmethod
    def convert_openai_to_claude37(payload):
        """
        Converts an OpenAI API request payload to the format expected by the
        Claude 3.7 /converse endpoint.
        """
        logger.debug(
            f"Original OpenAI payload for Claude 3.7 conversion: {json.dumps(payload, indent=2)}"
        )

        # Extract system message if present
        system_message = ""
        messages = payload.get("messages", [])
        if messages and messages[0].get("role") == "system":
            system_message = messages.pop(0).get("content", "")

        # Extract inference configuration parameters
        inference_config = {}
        if "max_tokens" in payload:
            # Ensure max_tokens is an integer
            try:
                inference_config["maxTokens"] = int(payload["max_tokens"])
            except (ValueError, TypeError):
                logger.warning(
                    f"Invalid value for max_tokens: {payload['max_tokens']}. Using default or omitting."
                )
        if "temperature" in payload:
            # Ensure temperature is a float
            try:
                inference_config["temperature"] = float(payload["temperature"])
            except (ValueError, TypeError):
                logger.warning(
                    f"Invalid value for temperature: {payload['temperature']}. Using default or omitting."
                )
        if "stop" in payload:
            stop_sequences = payload["stop"]
            if isinstance(stop_sequences, str):
                inference_config["stopSequences"] = [stop_sequences]
            elif isinstance(stop_sequences, list) and all(
                isinstance(s, str) for s in stop_sequences
            ):
                inference_config["stopSequences"] = stop_sequences
            else:
                logger.warning(
                    f"Unsupported type or content for 'stop' parameter: {stop_sequences}. Ignoring."
                )

        # Convert messages format
        converted_messages = []
        # The loop now iterates through the original messages list,
        # potentially including the system message if it wasn't removed earlier.
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")

            # Handle system, user, or assistant roles for inclusion in the messages list
            # Note: While the top-level 'system' parameter is standard for Claude /converse,
            # this modification includes the system message in the 'messages' array as requested.
            # This might deviate from the expected API usage.
            if role in ["user", "assistant"]:
                if content:
                    if isinstance(content, str):
                        # Convert string content to the required list of blocks format
                        converted_messages.append(
                            {"role": role, "content": [{"text": content}]}
                        )
                    elif isinstance(content, list):
                        # Validate that each item in the list is a correctly structured block
                        validated_content = []
                        for item in content:
                            if isinstance(item, dict) and "text" in item:
                                validated_content.append(item)
                            elif isinstance(item, str):
                                # Convert string item to block format
                                validated_content.append({"text": item})
                            else:
                                logger.warning(
                                    f"Skipping invalid content block for role {role}: {item}"
                                )

                        if validated_content:
                            converted_messages.append(
                                {"role": role, "content": validated_content}
                            )
                        else:
                            logger.warning(
                                f"Skipping message for role {role} due to all content blocks being invalid: {content}"
                            )
                    else:
                        logger.warning(
                            f"Skipping message for role {role} due to unsupported content type: {type(content)}"
                        )
                else:
                    logger.warning(
                        f"Skipping message for role {role} due to missing content: {msg}"
                    )
            else:
                # Skip any other unsupported roles
                logger.warning(
                    f"Skipping message with unsupported role for Claude /converse: {role}"
                )
                continue

        # add the system_message to the converted_messages as the first element
        if system_message:
            converted_messages.insert(
                0, {"role": "user", "content": [{"text": system_message}]}
            )

        # Construct the final Claude 3.7 payload
        claude_payload = {"messages": converted_messages}

        # Add inferenceConfig only if it's not empty
        if inference_config:
            claude_payload["inferenceConfig"] = inference_config

        # Add system message if it exists
        # Claude 3.7 doesn't support the system_message as a top-level parameter
        # if system_message:
        # Claude /converse API supports a top-level system prompt as a list of blocks
        # claude_payload["system"] = [{"text": system_message}]

        logger.debug(
            f"Converted Claude 3.7 payload: {json.dumps(claude_payload, indent=2)}"
        )
        return claude_payload

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
        """Converts a Claude Messages API request to a Google Gemini request."""
        logger.debug(
            f"Original Claude payload for Gemini conversion: {json.dumps(payload, indent=2)}"
        )

        gemini_contents = []
        system_prompt = payload.get("system", "")

        claude_messages = payload.get("messages", [])

        if system_prompt and claude_messages and claude_messages[0]["role"] == "user":
            first_user_content = claude_messages[0]["content"]
            if isinstance(first_user_content, list):
                first_user_content_text = " ".join(
                    c.get("text", "")
                    for c in first_user_content
                    if c.get("type") == "text"
                )
            else:
                first_user_content_text = first_user_content

            claude_messages[0]["content"] = (
                f"{system_prompt}\\n\\n{first_user_content_text}"
            )

        for message in claude_messages:
            role = "user" if message["role"] == "user" else "model"

            if isinstance(message["content"], list):
                content_text = " ".join(
                    c.get("text", "")
                    for c in message["content"]
                    if c.get("type") == "text"
                )
            else:
                content_text = message["content"]

            if gemini_contents and gemini_contents[-1]["role"] == role:
                gemini_contents[-1]["parts"]["text"] += f"\\n\\n{content_text}"
            else:
                gemini_contents.append({"role": role, "parts": {"text": content_text}})

        gemini_payload = {
            "contents": gemini_contents,
            "generation_config": {},
            "safety_settings": {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_LOW_AND_ABOVE",
            },
        }

        if "max_tokens" in payload:
            gemini_payload["generation_config"]["maxOutputTokens"] = payload[
                "max_tokens"
            ]
        if "temperature" in payload:
            gemini_payload["generation_config"]["temperature"] = payload["temperature"]
        if "tools" in payload and payload["tools"]:
            # Convert Claude tools format to Gemini tools format
            gemini_tools = []
            for tool in payload["tools"]:
                gemini_tool = {
                    "function_declarations": [
                        {
                            "name": tool["name"],
                            "description": tool["description"],
                            "parameters": tool["input_schema"],
                        }
                    ]
                }
                gemini_tools.append(gemini_tool)
            gemini_payload["tools"] = gemini_tools
            logger.debug(f"Converted {len(gemini_tools)} tools for Gemini format")

        logger.debug(
            f"Converted Gemini payload: {json.dumps(gemini_payload, indent=2)}"
        )
        return gemini_payload

    @staticmethod
    def convert_claude_request_for_bedrock(payload):
        """
        Convert a Claude Messages API request to Bedrock Claude format.
        Handle tool conversion for Bedrock compatibility.
        """
        logger.debug(
            f"Original Claude payload for Bedrock conversion: {json.dumps(payload, indent=2)}"
        )

        bedrock_payload = {}

        # Copy basic fields
        for field in [
            "model",
            "max_tokens",
            "temperature",
            "top_p",
            "top_k",
            "stop_sequences",
        ]:
            if field in payload:
                bedrock_payload[field] = payload[field]

        # Handle system field - keep as array format
        if "system" in payload:
            bedrock_payload["system"] = payload["system"]

        # Handle messages - remove cache_control fields
        if "messages" in payload:
            cleaned_messages = []
            for message in payload["messages"]:
                cleaned_message = {"role": message["role"]}

                # Handle content
                if isinstance(message["content"], list):
                    cleaned_content = []
                    for content_item in message["content"]:
                        if isinstance(content_item, dict):
                            # Remove cache_control field
                            cleaned_item = {
                                k: v
                                for k, v in content_item.items()
                                if k != "cache_control"
                            }
                            cleaned_content.append(cleaned_item)
                        else:
                            cleaned_content.append(content_item)
                    cleaned_message["content"] = cleaned_content
                else:
                    cleaned_message["content"] = [
                        {"type": "text", "text": message["content"]}
                    ]

                cleaned_messages.append(cleaned_message)
            bedrock_payload["messages"] = cleaned_messages

        # Handle tools conversion if present
        if "tools" in payload and payload["tools"]:
            bedrock_payload["tools"] = payload["tools"]
            logger.debug(f"Tools present in request: {len(payload['tools'])} tools")

        # Handle anthropic_beta if present (but not in payload, should be in headers)
        # Remove it from payload as it should be in headers only

        # Set anthropic_version if not present
        if "anthropic_version" not in bedrock_payload:
            bedrock_payload["anthropic_version"] = "bedrock-2023-05-31"

        logger.debug(
            f"Converted Bedrock Claude payload: {json.dumps(bedrock_payload, indent=2)}"
        )
        return bedrock_payload

    @staticmethod
    def convert_claude_to_openai(response, model):
        # Check if the model is Claude 3.7 or 4
        if Detector.is_claude_37_or_4(model):
            logger.info(
                f"Detected Claude 3.7/4 model ('{model}'), using convert_claude37_to_openai."
            )
            return Converters.convert_claude37_to_openai(response, model)

        # Proceed with the original Claude conversion logic for other models
        logger.info(f"Using standard Claude conversion for model '{model}'.")

        try:
            logger.info(
                f"Raw response from Claude API: {json.dumps(response, indent=4)}"
            )

            # Ensure the response contains the expected structure
            if "content" not in response or not isinstance(response["content"], list):
                raise ValueError(
                    "Invalid response structure: 'content' is missing or not a list"
                )

            first_content = response["content"][0]
            if not isinstance(first_content, dict) or "text" not in first_content:
                raise ValueError(
                    "Invalid response structure: 'content[0].text' is missing"
                )

            # Conversion logic from Claude API to OpenAI format
            openai_response = {
                "choices": [
                    {
                        "finish_reason": response.get("stop_reason", "stop"),
                        "index": 0,
                        "message": {
                            "content": first_content["text"],
                            "role": response.get("role", "assistant"),
                        },
                    }
                ],
                "created": int(time.time()),
                "id": response.get("id", "chatcmpl-unknown"),
                "model": response.get("model", "claude-v1"),
                "object": "chat.completion",
                "usage": {
                    "completion_tokens": response.get("usage", {}).get(
                        "output_tokens", 0
                    ),
                    "prompt_tokens": response.get("usage", {}).get("input_tokens", 0),
                    "total_tokens": response.get("usage", {}).get("input_tokens", 0)
                    + response.get("usage", {}).get("output_tokens", 0),
                },
            }
            logger.debug(
                f"Converted response to OpenAI format: {json.dumps(openai_response, indent=4)}"
            )
            return openai_response
        except Exception as e:
            logger.error(f"Error converting Claude response to OpenAI format: {e}")
            return {"error": "Invalid response from Claude API", "details": str(e)}

    @staticmethod
    def convert_claude37_to_openai(response, model_name="claude-3.7"):
        """
        Converts a Claude 3.7/4 /converse API response payload (non-streaming)
        to the format expected by the OpenAI Chat Completion API.
        """
        try:
            logger.debug(
                f"Raw response from Claude 3.7/4 API: {json.dumps(response, indent=2)}"
            )

            # Validate the overall response structure
            if not isinstance(response, dict):
                raise ValueError(
                    "Invalid response format: response is not a dictionary"
                )

            # --- Extract 'output' ---
            output = response.get("output")
            if not isinstance(output, dict):
                # Handle cases where the structure might differ unexpectedly
                # For now, strictly expect the documented /converse structure
                raise ValueError(
                    "Invalid response structure: 'output' field is missing or not a dictionary"
                )

            # --- Extract 'message' from 'output' ---
            message = output.get("message")
            if not isinstance(message, dict):
                raise ValueError(
                    "Invalid response structure: 'output.message' field is missing or not a dictionary"
                )

            # --- Extract 'content' list from 'message' ---
            content_list = message.get("content")
            if not isinstance(content_list, list) or not content_list:
                # Check if content is empty but maybe role/stopReason are still valid?
                # For now, require non-empty content for a standard completion response.
                raise ValueError(
                    "Invalid response structure: 'output.message.content' is missing, not a list, or empty"
                )

            # --- Extract text from the first content block ---
            # Assuming the primary response content is in the first block and is text.
            # More complex handling might be needed for multi-modal or tool use responses.
            first_content_block = content_list[0]
            if (
                not isinstance(first_content_block, dict)
                or "text" not in first_content_block
            ):
                # Log the type if it's not text, for debugging.
                block_type = (
                    first_content_block.get("type", "unknown")
                    if isinstance(first_content_block, dict)
                    else "not a dict"
                )
                logger.warning(
                    f"First content block is not of type 'text' or missing 'text' key. Type: {block_type}. Content: {first_content_block}"
                )
                # Decide how to handle non-text blocks. For now, raise error if no text found.
                # Find the first text block if available?
                content_text = None
                for block in content_list:
                    if (
                        isinstance(block, dict)
                        and block.get("type") == "text"
                        and "text" in block
                    ):
                        content_text = block["text"]
                        logger.info(
                            f"Found text content in block at index {content_list.index(block)}"
                        )
                        break
                if content_text is None:
                    raise ValueError(
                        "No text content block found in the response message content"
                    )
            else:
                content_text = first_content_block["text"]

            # --- Extract 'role' from 'message' ---
            message_role = message.get(
                "role", "assistant"
            )  # Default to assistant if missing

            # --- Extract 'usage' information ---
            usage = response.get("usage")
            if not isinstance(usage, dict):
                logger.warning(
                    "Usage information missing or invalid in Claude response. Setting tokens to 0."
                )
                usage = {}  # Use empty dict to avoid errors in .get() calls below

            input_tokens = usage.get("inputTokens", 0)
            output_tokens = usage.get("outputTokens", 0)
            # Claude 3.7/4 /converse should provide totalTokens, but calculate as fallback
            total_tokens = usage.get("totalTokens", input_tokens + output_tokens)

            # Extract cache/context tokens if available
            prompt_tokens_details = {}
            if "cacheReadInputTokens" in usage or "cacheCreationInputTokens" in usage:
                prompt_tokens_details["cached_tokens"] = usage.get(
                    "cacheReadInputTokens", 0
                )
                if usage.get("cacheCreationInputTokens", 0) > 0:
                    prompt_tokens_details["cache_creation_tokens"] = usage.get(
                        "cacheCreationInputTokens", 0
                    )

            # --- Map Claude stopReason to OpenAI finish_reason ---
            stop_reason_map = {
                "end_turn": "stop",
                "max_tokens": "length",
                "stop_sequence": "stop",
                "tool_use": "tool_calls",  # Map tool use if needed
                # Add other potential Claude stop reasons if they arise
            }
            claude_stop_reason = response.get("stopReason")
            finish_reason = stop_reason_map.get(
                claude_stop_reason, "stop"
            )  # Default to 'stop' if unknown or missing

            # --- Construct the OpenAI response ---
            openai_response = {
                "choices": [
                    {
                        "finish_reason": finish_reason,
                        "index": 0,
                        "message": {"content": content_text, "role": message_role},
                        # "logprobs": None, # Not available from Claude
                    }
                ],
                "created": int(time.time()),
                "id": f"chatcmpl-claude37-{random.randint(10000, 99999)}",  # More specific ID prefix
                "model": model_name,  # Use the provided model name
                "object": "chat.completion",
                "usage": {
                    "completion_tokens": output_tokens,
                    "prompt_tokens": input_tokens,
                    "total_tokens": total_tokens,
                },
            }

            # Add prompt_tokens_details if cache tokens are present
            if prompt_tokens_details:
                openai_response["usage"]["prompt_tokens_details"] = (
                    prompt_tokens_details
                )
                logger.debug(
                    f"Added prompt_tokens_details to response: {prompt_tokens_details}"
                )

            logger.debug(
                f"Converted response to OpenAI format: {json.dumps(openai_response, indent=2)}"
            )
            return openai_response

        except Exception as e:
            # Log the error with traceback for better debugging
            logger.error(
                f"Error converting Claude 3.7/4 response to OpenAI format: {e}",
                exc_info=True,
            )
            # Log the problematic response structure that caused the error
            logger.error(
                f"Problematic Claude response structure: {json.dumps(response, indent=2)}"
            )
            # Return an error structure compliant with OpenAI format
            return {
                "object": "error",
                "message": f"Failed to convert Claude 3.7/4 response to OpenAI format. Error: {str(e)}. Check proxy logs for details.",
                "type": "proxy_conversion_error",
                "param": None,
                "code": None,
                # Optionally include parts of the OpenAI structure if needed by the client
                # "choices": [],
                # "created": int(time.time()),
                # "id": f"chatcmpl-error-{random.randint(10000, 99999)}",
                # "model": model_name,
                # "usage": {"completion_tokens": 0, "prompt_tokens": 0, "total_tokens": 0},
            }

    @staticmethod
    def convert_claude_chunk_to_openai(chunk, model):
        try:
            # Log the raw chunk received
            # Log the raw chunk received only if it's a 3.7 model
            logger.info(f"{model} Raw Claude chunk received: {chunk}")
            # Parse the Claude chunk
            data = json.loads(chunk.replace("data: ", "").strip())

            # Initialize the OpenAI chunk structure
            openai_chunk = {
                "choices": [{"delta": {}, "finish_reason": None, "index": 0}],
                "created": int(time.time()),
                "id": data.get("message", {}).get("id", "chatcmpl-unknown"),
                "model": "claude-v1",
                "object": "chat.completion.chunk",
                "system_fingerprint": "fp_36b0c83da2",
            }

            # Map Claude's content to OpenAI's delta
            if data.get("type") == "content_block_delta":
                openai_chunk["choices"][0]["delta"]["content"] = data["delta"]["text"]
            elif (
                data.get("type") == "message_delta"
                and data["delta"]["stop_reason"] == "end_turn"
            ):
                openai_chunk["choices"][0]["finish_reason"] = "stop"

            return f"data: {json.dumps(openai_chunk)}\n\n"
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            return 'data: {"error": "Invalid JSON format"}\n\n'
        except Exception as e:
            logger.error(f"Error processing chunk: {e}")
            return f'data: {{"error": "Error processing chunk"}}\n\n'

    @staticmethod
    def convert_claude37_chunk_to_openai(claude_chunk, model_name):
        """
        Converts a single parsed Claude 3.7/4/4.5 /converse-stream chunk (dictionary)
        into an OpenAI-compatible Server-Sent Event (SSE) string.
        Returns None if the chunk doesn't map to an OpenAI event (e.g., metadata).
        """
        try:
            # Generate a consistent-ish ID for the stream parts
            # In a real scenario, this ID should be generated once per request stream
            # and potentially passed down or managed in the calling context.
            stream_id = f"chatcmpl-claude37-{random.randint(10000, 99999)}"
            created_time = int(time.time())

            openai_chunk_payload = {
                "id": stream_id,
                "object": "chat.completion.chunk",
                "created": created_time,
                "model": model_name,
                "choices": [
                    {
                        "index": 0,
                        "delta": {},
                        "finish_reason": None,
                        # "logprobs": None # Not available from Claude
                    }
                ],
                # "system_fingerprint": None # Not typically sent in chunks
            }

            # Determine chunk type based on the first key in the dictionary
            # claude_chunk is string, so need to parse it
            if isinstance(claude_chunk, str):
                try:
                    # claude_chunk = json.dumps(claude_chunk.replace("data: ", "").strip())
                    logger.info(f"Parsed Claude chunk: {claude_chunk}")
                    claude_chunk = json.loads(claude_chunk)
                    logger.info(
                        f"Decoded Claude chunk: {json.dumps(claude_chunk, indent=2)}"
                    )
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error: {e}")
                    return None

            if not isinstance(claude_chunk, dict) or not claude_chunk:
                logger.warning(
                    f"Invalid or empty Claude chunk received: {claude_chunk}"
                )
                return None

            chunk_type = next(iter(claude_chunk))  # Get the first key

            if chunk_type == "messageStart":
                # Extract role, default to assistant if not present
                role = claude_chunk.get("messageStart", {}).get("role", "assistant")
                openai_chunk_payload["choices"][0]["delta"]["role"] = role
                logger.debug(f"Converted messageStart chunk: {openai_chunk_payload}")

            elif chunk_type == "contentBlockDelta":
                # Extract text delta
                text_delta = (
                    claude_chunk.get("contentBlockDelta", {})
                    .get("delta", {})
                    .get("text")
                )
                if (
                    text_delta is not None
                ):  # Send even if empty string delta? OpenAI usually does.
                    openai_chunk_payload["choices"][0]["delta"]["content"] = text_delta
                    logger.debug(
                        f"Converted contentBlockDelta chunk: {openai_chunk_payload}"
                    )
                else:
                    # If delta or text is missing, maybe log but don't send?
                    logger.debug(
                        f"Ignoring contentBlockDelta without text: {claude_chunk}"
                    )
                    return None  # Don't send chunk if no actual text delta

            elif chunk_type == "messageStop":
                # Extract stop reason
                stop_reason = claude_chunk.get("messageStop", {}).get("stopReason")
                # Map Claude stopReason to OpenAI finish_reason
                stop_reason_map = {
                    "end_turn": "stop",
                    "max_tokens": "length",
                    "stop_sequence": "stop",
                    "tool_use": "tool_calls",  # Map tool use if needed
                    # Add other potential Claude stop reasons if they arise
                }
                finish_reason = stop_reason_map.get(stop_reason)
                if finish_reason:
                    openai_chunk_payload["choices"][0]["finish_reason"] = finish_reason
                    # Delta should be empty or null for the final chunk with finish_reason
                    openai_chunk_payload["choices"][0][
                        "delta"
                    ] = {}  # Ensure delta is empty
                    logger.debug(f"Converted messageStop chunk: {openai_chunk_payload}")
                else:
                    logger.warning(
                        f"Unmapped or missing stopReason in messageStop: {stop_reason}. Chunk: {claude_chunk}"
                    )
                    # Decide if to send a default stop or ignore
                    # Sending with finish_reason=null might be confusing. Let's ignore.
                    return None

            elif chunk_type in ["contentBlockStart", "contentBlockStop", "metadata"]:
                # These Claude events don't have a direct OpenAI chunk equivalent
                # containing message delta or finish reason. Ignore them for streaming output.
                # Metadata chunk should be handled separately in the calling function (`generate`)
                # to extract usage information.
                logger.debug(
                    f"Ignoring Claude chunk type for OpenAI stream: {chunk_type}"
                )
                return None
            else:
                logger.warning(
                    f"Unknown Claude 3.7/4 chunk type encountered: {chunk_type}. Chunk: {claude_chunk}"
                )
                return None

            # Format as SSE string if a valid payload was constructed
            sse_string = f"data: {json.dumps(openai_chunk_payload)}\n\n"
            return sse_string

        except Exception as e:
            logger.error(
                f"Error converting Claude 3.7/4 chunk to OpenAI format: {e}",
                exc_info=True,
            )
            logger.error(
                f"Problematic Claude chunk: {json.dumps(claude_chunk, indent=2)}"
            )
            # Optionally return an error chunk in SSE format to the client
            error_payload = {
                "id": f"chatcmpl-error-{random.randint(10000, 99999)}",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": model_name,
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "content": f"[PROXY ERROR: Failed to convert upstream chunk - {str(e)}]"
                        },
                        "finish_reason": "stop",
                    }
                ],
            }
            return f"data: {json.dumps(error_payload)}\n\n"

    @staticmethod
    def convert_openai_to_gemini(payload):
        """
        Converts an OpenAI API request payload to the format expected by the
        Google Vertex AI Gemini generateContent endpoint.
        """
        logger.info(
            f"Original OpenAI payload for Gemini conversion: {json.dumps(payload, indent=2)}"
        )

        # Extract system message if present
        system_message = ""
        messages = payload.get("messages", [])
        if messages and messages[0].get("role") == "system":
            system_message = messages.pop(0).get("content", "")

        # Build generation config
        generation_config = {}
        if "max_tokens" in payload:
            try:
                generation_config["maxOutputTokens"] = int(payload["max_tokens"])
            except (ValueError, TypeError):
                logger.warning(
                    f"Invalid value for max_tokens: {payload['max_tokens']}. Using default or omitting."
                )

        if "temperature" in payload:
            try:
                generation_config["temperature"] = float(payload["temperature"])
            except (ValueError, TypeError):
                logger.warning(
                    f"Invalid value for temperature: {payload['temperature']}. Using default or omitting."
                )

        if "top_p" in payload:
            try:
                generation_config["topP"] = float(payload["top_p"])
            except (ValueError, TypeError):
                logger.warning(
                    f"Invalid value for top_p: {payload['top_p']}. Using default or omitting."
                )

        # Convert messages to Gemini format
        # For single message case (most common), create a simple structure
        if len(messages) == 1 and messages[0].get("role") == "user":
            # Single user message case - match the curl example structure
            user_content = messages[0].get("content", "")

            # Handle different content types (string or list)
            if isinstance(user_content, list):
                # Extract text from content blocks
                text_content = ""
                for block in user_content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text_content += block.get("text", "")
                    elif isinstance(block, str):
                        text_content += block
                user_content = text_content
            elif not isinstance(user_content, str):
                # Convert to string if it's neither list nor string
                user_content = str(user_content)

            # If there's a system message, prepend it to the user content
            if system_message:
                user_content = system_message + "\n\n" + user_content

            gemini_contents = {"role": "user", "parts": {"text": user_content}}
        else:
            # Multiple messages case - use array format
            gemini_contents = []

            # Add system message as the first user message if it exists
            if system_message:
                gemini_contents.append(
                    {"role": "user", "parts": {"text": system_message}}
                )

            # Process remaining messages
            for msg in messages:
                role = msg.get("role")
                content = msg.get("content", "")

                # Map OpenAI roles to Gemini roles
                if role == "user":
                    gemini_role = "user"
                elif role == "assistant":
                    gemini_role = "model"
                else:
                    logger.warning(
                        f"Skipping message with unsupported role for Gemini: {role}"
                    )
                    continue

                if content:
                    # Handle different content types (string or list)
                    if isinstance(content, list):
                        # Extract text from content blocks
                        text_content = ""
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                text_content += block.get("text", "")
                            elif isinstance(block, str):
                                text_content += block
                        content = text_content
                    elif not isinstance(content, str):
                        # Convert to string if it's neither list nor string
                        content = str(content)

                    # Check if we can merge with the previous message (same role)
                    if gemini_contents and gemini_contents[-1]["role"] == gemini_role:
                        # Merge with previous message
                        if isinstance(gemini_contents[-1]["parts"], dict):
                            gemini_contents[-1]["parts"]["text"] += "\n\n" + content
                        else:
                            # Handle case where parts might be a list (future extension)
                            gemini_contents[-1]["parts"] = {
                                "text": gemini_contents[-1]["parts"]["text"]
                                + "\n\n"
                                + content
                            }
                    else:
                        # Add new message
                        gemini_contents.append(
                            {"role": gemini_role, "parts": {"text": content}}
                        )

        # Build safety settings (as a single object to match the curl example)
        safety_settings = {
            "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
            "threshold": "BLOCK_LOW_AND_ABOVE",
        }

        # Construct the final Gemini payload
        gemini_payload = {"contents": gemini_contents}

        # Add generation config if not empty
        if generation_config:
            gemini_payload["generation_config"] = generation_config

        # Add safety settings
        gemini_payload["safety_settings"] = safety_settings

        logger.debug(
            f"Converted Gemini payload: {json.dumps(gemini_payload, indent=2)}"
        )
        return gemini_payload

    @staticmethod
    def convert_gemini_to_openai(response, model_name="gemini-pro"):
        """
        Converts a Gemini generateContent API response payload (non-streaming)
        to the format expected by the OpenAI Chat Completion API.
        """
        try:
            logger.debug(
                f"Raw response from Gemini API: {json.dumps(response, indent=2)}"
            )

            # Validate the overall response structure
            if not isinstance(response, dict):
                raise ValueError(
                    "Invalid response format: response is not a dictionary"
                )

            # Extract candidates
            candidates = response.get("candidates", [])
            if not candidates:
                raise ValueError("Invalid response structure: no candidates found")

            # Get the first candidate
            first_candidate = candidates[0]
            if not isinstance(first_candidate, dict):
                raise ValueError(
                    "Invalid response structure: candidate is not a dictionary"
                )

            # Extract content from the candidate
            content = first_candidate.get("content", {})
            if not isinstance(content, dict):
                raise ValueError(
                    "Invalid response structure: content is not a dictionary"
                )

            # Extract parts from content
            parts = content.get("parts", [])
            if not parts:
                raise ValueError(
                    "Invalid response structure: no parts found in content"
                )

            # Extract text from the first part
            first_part = parts[0]
            if not isinstance(first_part, dict) or "text" not in first_part:
                raise ValueError(
                    "Invalid response structure: no text found in first part"
                )

            content_text = first_part["text"]

            # Extract finish reason
            finish_reason_map = {
                "STOP": "stop",
                "MAX_TOKENS": "length",
                "SAFETY": "content_filter",
                "RECITATION": "content_filter",
                "OTHER": "stop",
            }
            gemini_finish_reason = first_candidate.get("finishReason", "STOP")
            finish_reason = finish_reason_map.get(gemini_finish_reason, "stop")

            # Extract usage information
            usage_metadata = response.get("usageMetadata", {})
            prompt_tokens = usage_metadata.get("promptTokenCount", 0)
            completion_tokens = usage_metadata.get("candidatesTokenCount", 0)
            total_tokens = usage_metadata.get(
                "totalTokenCount", prompt_tokens + completion_tokens
            )

            # Construct the OpenAI response
            openai_response = {
                "choices": [
                    {
                        "finish_reason": finish_reason,
                        "index": 0,
                        "message": {"content": content_text, "role": "assistant"},
                    }
                ],
                "created": int(time.time()),
                "id": f"chatcmpl-gemini-{random.randint(10000, 99999)}",
                "model": model_name,
                "object": "chat.completion",
                "usage": {
                    "completion_tokens": completion_tokens,
                    "prompt_tokens": prompt_tokens,
                    "total_tokens": total_tokens,
                },
            }

            logger.debug(
                f"Converted response to OpenAI format: {json.dumps(openai_response, indent=2)}"
            )
            return openai_response

        except Exception as e:
            logger.error(
                f"Error converting Gemini response to OpenAI format: {e}", exc_info=True
            )
            logger.error(
                f"Problematic Gemini response structure: {json.dumps(response, indent=2)}"
            )
            return {
                "object": "error",
                "message": f"Failed to convert Gemini response to OpenAI format. Error: {str(e)}. Check proxy logs for details.",
                "type": "proxy_conversion_error",
                "param": None,
                "code": None,
            }

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
            stop_reason_map = {
                "STOP": "end_turn",
                "MAX_TOKENS": "max_tokens",
                "SAFETY": "stop_sequence",
                "RECITATION": "stop_sequence",
                "OTHER": "stop_sequence",
            }
            claude_stop_reason = stop_reason_map.get(
                gemini_finish_reason, "stop_sequence"
            )

            # Extract usage
            usage_metadata = response.get("usageMetadata", {})
            prompt_tokens = usage_metadata.get("promptTokenCount", 0)
            completion_tokens = usage_metadata.get("candidatesTokenCount", 0)

            claude_response = {
                "id": f"msg_gemini_{random.randint(10000, 99999)}",
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
                                "id", f"toolu_openai_{random.randint(10000, 99999)}"
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
            stop_reason_map = {
                "stop": "end_turn",
                "length": "max_tokens",
                "content_filter": "stop_sequence",
                "tool_calls": "tool_use",
            }
            claude_stop_reason = stop_reason_map.get(
                openai_finish_reason, "stop_sequence"
            )

            # Extract usage
            usage = response.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)

            claude_response = {
                "id": response.get("id", f"msg_openai_{random.randint(10000, 99999)}"),
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
        """
        Converts a single Gemini streaming chunk to OpenAI-compatible SSE format.
        Returns None if the chunk doesn't map to an OpenAI event.
        """
        try:
            # Generate a consistent ID for the stream
            stream_id = f"chatcmpl-gemini-{random.randint(10000, 99999)}"
            created_time = int(time.time())

            openai_chunk_payload = {
                "id": stream_id,
                "object": "chat.completion.chunk",
                "created": created_time,
                "model": model_name,
                "choices": [{"index": 0, "delta": {}, "finish_reason": None}],
            }

            # Parse the chunk if it's a string
            if isinstance(gemini_chunk, str):
                try:
                    gemini_chunk = json.loads(gemini_chunk)
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error: {e}")
                    return None

            if not isinstance(gemini_chunk, dict):
                logger.warning(f"Invalid Gemini chunk received: {gemini_chunk}")
                return None

            # Extract candidates
            candidates = gemini_chunk.get("candidates", [])
            if not candidates:
                return None

            first_candidate = candidates[0]

            # Check for finish reason
            if "finishReason" in first_candidate:
                finish_reason_map = {
                    "STOP": "stop",
                    "MAX_TOKENS": "length",
                    "SAFETY": "content_filter",
                    "RECITATION": "content_filter",
                    "OTHER": "stop",
                }
                gemini_finish_reason = first_candidate["finishReason"]
                finish_reason = finish_reason_map.get(gemini_finish_reason, "stop")
                openai_chunk_payload["choices"][0]["finish_reason"] = finish_reason
                # openai_chunk_payload["choices"][0]["delta"] = {}
                # Extract content delta
                content = first_candidate.get("content", {})
                parts = content.get("parts", [])

                if parts and "text" in parts[0]:
                    text_delta = parts[0]["text"]
                    logger.info(f"Gemini text delta: {text_delta}")
                    openai_chunk_payload["choices"][0]["delta"]["content"] = text_delta
            else:
                # Extract content delta
                content = first_candidate.get("content", {})
                parts = content.get("parts", [])

                if parts and "text" in parts[0]:
                    text_delta = parts[0]["text"]
                    logger.info(f"Gemini text delta: {text_delta}")
                    openai_chunk_payload["choices"][0]["delta"]["content"] = text_delta

            # Format as SSE string
            sse_string = f"data: {json.dumps(openai_chunk_payload)}\n\n"
            return sse_string

        except Exception as e:
            logger.error(
                f"Error converting Gemini chunk to OpenAI format: {e}", exc_info=True
            )
            error_payload = {
                "id": f"chatcmpl-error-{random.randint(10000, 99999)}",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": model_name,
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "content": f"[PROXY ERROR: Failed to convert upstream chunk - {str(e)}]"
                        },
                        "finish_reason": "stop",
                    }
                ],
            }
            return f"data: {json.dumps(error_payload)}\n\n"
