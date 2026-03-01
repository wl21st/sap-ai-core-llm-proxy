"""Gemini conversion helpers."""

from __future__ import annotations

import json
from logging import Logger

from utils.logging_utils import get_server_logger

logger: Logger = get_server_logger(__name__)


def from_openai(payload: dict) -> dict:
    """Convert an OpenAI chat completion request to Gemini generateContent."""
    logger.info(
        "Original OpenAI payload for Gemini conversion: %s",
        json.dumps(payload, indent=2),
    )

    system_message = ""
    messages = payload.get("messages", [])
    if messages and messages[0].get("role") == "system":
        system_message = messages.pop(0).get("content", "")

    generation_config: dict[str, object] = {}
    if "max_tokens" in payload:
        try:
            generation_config["maxOutputTokens"] = int(payload["max_tokens"])
        except (ValueError, TypeError):
            logger.warning(
                "Invalid value for max_tokens: %s. Using default or omitting.",
                payload["max_tokens"],
            )

    if "temperature" in payload:
        try:
            generation_config["temperature"] = float(payload["temperature"])
        except (ValueError, TypeError):
            logger.warning(
                "Invalid value for temperature: %s. Using default or omitting.",
                payload["temperature"],
            )

    if "top_p" in payload:
        try:
            generation_config["topP"] = float(payload["top_p"])
        except (ValueError, TypeError):
            logger.warning(
                "Invalid value for top_p: %s. Using default or omitting.",
                payload["top_p"],
            )

    if len(messages) == 1 and messages[0].get("role") == "user":
        user_content = messages[0].get("content", "")

        if isinstance(user_content, list):
            text_content = ""
            for block in user_content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_content += block.get("text", "")
                elif isinstance(block, str):
                    text_content += block
            user_content = text_content
        elif not isinstance(user_content, str):
            user_content = str(user_content)

        if system_message:
            user_content = system_message + "\n\n" + user_content

        gemini_contents: object = {"role": "user", "parts": {"text": user_content}}
    else:
        gemini_contents = []

        if system_message:
            gemini_contents.append({"role": "user", "parts": {"text": system_message}})

        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "")

            if role == "user":
                gemini_role = "user"
            elif role == "assistant":
                gemini_role = "model"
            else:
                logger.warning(
                    "Skipping message with unsupported role for Gemini: %s", role
                )
                continue

            if content:
                if isinstance(content, list):
                    text_content = ""
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text_content += block.get("text", "")
                        elif isinstance(block, str):
                            text_content += block
                    content = text_content
                elif not isinstance(content, str):
                    content = str(content)

                if gemini_contents and gemini_contents[-1]["role"] == gemini_role:
                    if isinstance(gemini_contents[-1]["parts"], dict):
                        gemini_contents[-1]["parts"]["text"] += "\n\n" + content
                    else:
                        gemini_contents[-1]["parts"] = {
                            "text": gemini_contents[-1]["parts"]["text"]
                            + "\n\n"
                            + content
                        }
                else:
                    gemini_contents.append(
                        {"role": gemini_role, "parts": {"text": content}}
                    )

    safety_settings = {
        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "threshold": "BLOCK_LOW_AND_ABOVE",
    }

    gemini_payload = {"contents": gemini_contents}

    if generation_config:
        gemini_payload["generation_config"] = generation_config

    gemini_payload["safety_settings"] = safety_settings

    logger.debug("Converted Gemini payload: %s", json.dumps(gemini_payload, indent=2))
    return gemini_payload


def from_claude(payload: dict) -> dict:
    """Convert a Claude Messages request to Gemini generateContent."""
    logger.debug(
        "Original Claude payload for Gemini conversion: %s",
        json.dumps(payload, indent=2),
    )

    gemini_contents = []
    system_prompt = payload.get("system", "")

    claude_messages = payload.get("messages", [])

    if system_prompt and claude_messages and claude_messages[0]["role"] == "user":
        first_user_content = claude_messages[0]["content"]
        if isinstance(first_user_content, list):
            first_user_content_text = " ".join(
                c.get("text", "") for c in first_user_content if c.get("type") == "text"
            )
        else:
            first_user_content_text = first_user_content

        claude_messages[0]["content"] = f"{system_prompt}\n\n{first_user_content_text}"

    for message in claude_messages:
        role = "user" if message["role"] == "user" else "model"

        if isinstance(message["content"], list):
            content_text = " ".join(
                c.get("text", "") for c in message["content"] if c.get("type") == "text"
            )
        else:
            content_text = message["content"]

        if gemini_contents and gemini_contents[-1]["role"] == role:
            gemini_contents[-1]["parts"]["text"] += f"\n\n{content_text}"
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
        gemini_payload["generation_config"]["maxOutputTokens"] = payload["max_tokens"]
    if "temperature" in payload:
        gemini_payload["generation_config"]["temperature"] = payload["temperature"]
    if "tools" in payload and payload["tools"]:
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
        logger.debug("Converted %s tools for Gemini format", len(gemini_tools))

    logger.debug(
        "Converted Gemini payload: %s",
        json.dumps(gemini_payload, indent=2),
    )
    return gemini_payload
