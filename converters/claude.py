"""Claude/Bedrock conversion helpers."""

from __future__ import annotations

import json
from logging import Logger

from converters.mappings import API_VERSION_BEDROCK_2023_05_31, STOP_REASON_MAP
from utils.logging_utils import get_server_logger

logger: Logger = get_server_logger(__name__)


def _sanitize_content_block(content_item: dict) -> dict | None:
    if not isinstance(content_item, dict):
        return None

    text_content = content_item.get("text")
    if not text_content:
        return None

    metadata_fields = [k for k in content_item.keys() if k not in ["type", "text"]]
    if metadata_fields:
        logger.warning(
            "Stripping metadata from content block during Claude 3.7 conversion: %s. "
            "SAP AI Core does not support these fields.",
            metadata_fields,
        )

    return {"text": text_content}


def _extract_text_from_content(content: object) -> str:
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        texts = []
        for item in content:
            if isinstance(item, str):
                texts.append(item)
            elif isinstance(item, dict) and "text" in item:
                texts.append(item["text"])
        return " ".join(texts) if texts else ""

    return ""


def from_openai(payload: dict) -> dict:
    """Convert OpenAI chat completion request to Claude Messages format."""
    system_message = ""
    messages = payload["messages"]
    if messages and messages[0]["role"] == "system":
        raw_system_content = messages.pop(0)["content"]
        system_message = _extract_text_from_content(raw_system_content)

    for msg in messages:
        if isinstance(msg.get("content"), list):
            sanitized_content = []
            for item in msg["content"]:
                if isinstance(item, dict) and "text" in item:
                    sanitized = _sanitize_content_block(item)
                    if sanitized:
                        sanitized_content.append(sanitized)
                elif isinstance(item, str):
                    sanitized_content.append({"text": item})
            msg["content"] = sanitized_content

    claude_payload = {
        "anthropic_version": API_VERSION_BEDROCK_2023_05_31,
        "max_tokens": payload.get("max_tokens")
        or payload.get("max_completion_tokens", 200000),
        "temperature": payload.get("temperature", 1.0),
        "system": system_message,
        "messages": messages,
    }

    if "tools" in payload and payload["tools"]:
        claude_payload["tools"] = payload["tools"]
        logger.debug("Tools present in request: %s tools", len(payload["tools"]))

    return claude_payload


def claude_converse_from_openai(payload: dict) -> dict:
    """Convert OpenAI chat completion request to Claude /converse format."""
    logger.debug(
        "Original OpenAI payload for Claude 3.7 conversion: %s",
        json.dumps(payload, indent=2),
    )

    system_message = ""
    messages = payload.get("messages", [])
    if messages and messages[0].get("role") == "system":
        raw_system_content = messages.pop(0).get("content", "")
        system_message = _extract_text_from_content(raw_system_content)

    inference_config = {}
    if "max_tokens" in payload or "max_completion_tokens" in payload:
        max_tokens_value = payload.get("max_tokens") or payload.get(
            "max_completion_tokens"
        )
        try:
            inference_config["maxTokens"] = int(max_tokens_value)
        except (ValueError, TypeError):
            logger.warning(
                "Invalid value for max_tokens: %s. Using default or omitting.",
                max_tokens_value,
            )
    if "temperature" in payload:
        try:
            inference_config["temperature"] = float(payload["temperature"])
        except (ValueError, TypeError):
            logger.warning(
                "Invalid value for temperature: %s. Using default or omitting.",
                payload["temperature"],
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
                "Unsupported type or content for 'stop' parameter: %s. Ignoring.",
                stop_sequences,
            )

    converted_messages = []
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content")

        if role in ["user", "assistant"]:
            if content:
                if isinstance(content, str):
                    converted_messages.append(
                        {"role": role, "content": [{"text": content}]}
                    )
                elif isinstance(content, list):
                    validated_content = []
                    for item in content:
                        if isinstance(item, dict) and "text" in item:
                            sanitized = _sanitize_content_block(item)
                            if sanitized:
                                validated_content.append(sanitized)
                        elif isinstance(item, str):
                            validated_content.append({"text": item})
                        else:
                            logger.warning(
                                "Skipping invalid content block for role %s: %s",
                                role,
                                item,
                            )

                    if validated_content:
                        converted_messages.append(
                            {"role": role, "content": validated_content}
                        )
                    else:
                        logger.warning(
                            "Skipping message for role %s due to all content blocks being invalid: %s",
                            role,
                            content,
                        )
                else:
                    logger.warning(
                        "Skipping message for role %s due to unsupported content type: %s",
                        role,
                        type(content),
                    )
            else:
                logger.warning(
                    "Skipping message for role %s due to missing content: %s",
                    role,
                    msg,
                )
        else:
            logger.warning(
                "Skipping message with unsupported role for Claude /converse: %s",
                role,
            )
            continue

    if system_message:
        converted_messages.insert(
            0, {"role": "user", "content": [{"text": system_message}]}
        )

    claude_payload: dict[str, object] = {"messages": converted_messages}

    if inference_config:
        claude_payload["inferenceConfig"] = inference_config

    if "tools" in payload and payload["tools"]:
        claude_payload["tools"] = payload["tools"]
        logger.debug(
            "Tools present in request: %s tools forwarded to SAP AI Core",
            len(payload["tools"]),
        )

    logger.debug(
        "Converted Claude 3.7 payload: %s",
        json.dumps(claude_payload, indent=2),
    )
    return claude_payload


def claude_bedrock_from_claude(payload: dict) -> dict:
    """Convert a Claude Messages API request to Bedrock Claude format."""
    logger.debug(
        "Original Claude payload for Bedrock conversion: %s",
        json.dumps(payload, indent=2),
    )

    bedrock_payload: dict[str, object] = {}

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

    if "system" in payload:
        bedrock_payload["system"] = payload["system"]

    if "messages" in payload:
        cleaned_messages = []
        for message in payload["messages"]:
            cleaned_message = {"role": message["role"]}

            if isinstance(message["content"], list):
                cleaned_content = []
                for content_item in message["content"]:
                    if isinstance(content_item, dict):
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

    if "tools" in payload and payload["tools"]:
        bedrock_payload["tools"] = payload["tools"]
        logger.debug("Tools present in request: %s tools", len(payload["tools"]))

    if "anthropic_version" not in bedrock_payload:
        bedrock_payload["anthropic_version"] = API_VERSION_BEDROCK_2023_05_31

    logger.debug(
        "Converted Bedrock Claude payload: %s",
        json.dumps(bedrock_payload, indent=2),
    )
    return bedrock_payload
