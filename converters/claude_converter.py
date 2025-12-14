"""Claude format converter for OpenAI ↔ Claude conversions.

This module handles bidirectional conversion between OpenAI Chat Completions
format and Anthropic Claude Messages API format, including both standard
Claude (3.5) and newer Claude (3.7, 4, 4.5) formats.
"""

import logging
import time
import json
from typing import Dict, Any, List, Optional

from converters.base import BidirectionalConverter
from models import ModelDetector


class ClaudeConverter(BidirectionalConverter):
    """Converter for OpenAI ↔ Claude format transformations.
    
    Supports:
    - OpenAI → Claude 3.5 (invoke endpoint)
    - OpenAI → Claude 3.7/4/4.5 (converse endpoint)
    - Claude → OpenAI (response conversion)
    
    The converter automatically detects the Claude version and applies
    the appropriate conversion logic.
    """
    
    def get_source_format(self) -> str:
        """Get source format name."""
        return "openai"
    
    def get_target_format(self) -> str:
        """Get target format name."""
        return "claude"
    
    def convert_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Convert OpenAI request to Claude format.
        
        Automatically detects Claude version from model name and applies
        appropriate conversion (invoke vs converse format).
        
        Args:
            payload: OpenAI Chat Completions request payload
            
        Returns:
            Claude Messages API request payload
            
        Raises:
            ValueError: If payload is invalid
        """
        model = payload.get("model", "")
        
        # Detect Claude version and use appropriate converter
        if ModelDetector.is_claude_37_or_4(model):
            return self._convert_to_claude37(payload)
        else:
            return self._convert_to_claude35(payload)
    
    def _convert_to_claude35(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Convert OpenAI request to Claude 3.5 format (invoke endpoint).
        
        Args:
            payload: OpenAI request payload
            
        Returns:
            Claude 3.5 request payload
        """
        # Extract system message if present
        system_message = ""
        messages = payload.get("messages", []).copy()
        
        if messages and messages[0].get("role") == "system":
            system_message = messages.pop(0).get("content", "")
        
        # Build Claude payload
        claude_payload = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": payload.get("max_tokens", 4096000),
            "temperature": payload.get("temperature", 1.0),
            "system": system_message,
            "messages": messages,
        }
        
        logging.debug(f"Converted to Claude 3.5 format: {json.dumps(claude_payload, indent=2)}")
        return claude_payload
    
    def _convert_to_claude37(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Convert OpenAI request to Claude 3.7/4/4.5 format (converse endpoint).
        
        Args:
            payload: OpenAI request payload
            
        Returns:
            Claude 3.7+ request payload
        """
        logging.debug(f"Converting to Claude 3.7+ format: {json.dumps(payload, indent=2)}")
        
        # Extract system message if present
        system_message = ""
        messages = payload.get("messages", []).copy()
        
        if messages and messages[0].get("role") == "system":
            system_message = messages.pop(0).get("content", "")
        
        # Build inference configuration
        inference_config = {}
        
        if "max_tokens" in payload:
            try:
                inference_config["maxTokens"] = int(payload["max_tokens"])
            except (ValueError, TypeError):
                logging.warning(f"Invalid max_tokens: {payload['max_tokens']}")
        
        if "temperature" in payload:
            try:
                inference_config["temperature"] = float(payload["temperature"])
            except (ValueError, TypeError):
                logging.warning(f"Invalid temperature: {payload['temperature']}")
        
        if "stop" in payload:
            stop_sequences = payload["stop"]
            if isinstance(stop_sequences, str):
                inference_config["stopSequences"] = [stop_sequences]
            elif isinstance(stop_sequences, list):
                inference_config["stopSequences"] = stop_sequences
        
        # Convert messages to converse format
        converted_messages = []
        
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")
            
            if role not in ["user", "assistant"]:
                logging.warning(f"Skipping unsupported role: {role}")
                continue
            
            if not content:
                logging.warning(f"Skipping message with no content: {msg}")
                continue
            
            # Convert content to list of blocks format
            if isinstance(content, str):
                converted_messages.append({
                    "role": role,
                    "content": [{"text": content}]
                })
            elif isinstance(content, list):
                validated_content = []
                for item in content:
                    if isinstance(item, dict) and "text" in item:
                        validated_content.append(item)
                    elif isinstance(item, str):
                        validated_content.append({"text": item})
                    else:
                        logging.warning(f"Skipping invalid content block: {item}")
                
                if validated_content:
                    converted_messages.append({
                        "role": role,
                        "content": validated_content
                    })
        
        # Prepend system message as first user message if present
        if system_message:
            converted_messages.insert(0, {
                "role": "user",
                "content": [{"text": system_message}]
            })
        
        # Build final payload
        claude_payload = {"messages": converted_messages}
        
        if inference_config:
            claude_payload["inferenceConfig"] = inference_config
        
        logging.debug(f"Converted to Claude 3.7+ format: {json.dumps(claude_payload, indent=2)}")
        return claude_payload
    
    def convert_response(self, response: Dict[str, Any], model: str) -> Dict[str, Any]:
        """Convert Claude response to OpenAI format.
        
        Automatically detects Claude version and applies appropriate conversion.
        
        Args:
            response: Claude Messages API response
            model: Model name for version detection
            
        Returns:
            OpenAI Chat Completions response
            
        Raises:
            ValueError: If response is invalid
        """
        # Detect Claude version
        if ModelDetector.is_claude_37_or_4(model):
            return self._convert_claude37_response(response, model)
        else:
            return self._convert_claude35_response(response, model)
    
    def _convert_claude35_response(self, response: Dict[str, Any], model: str) -> Dict[str, Any]:
        """Convert Claude 3.5 response to OpenAI format.
        
        Args:
            response: Claude 3.5 response
            model: Model name
            
        Returns:
            OpenAI response
        """
        try:
            logging.debug(f"Converting Claude 3.5 response: {json.dumps(response, indent=2)}")
            
            # Validate response structure
            if "content" not in response or not isinstance(response["content"], list):
                raise ValueError("Invalid response: 'content' missing or not a list")
            
            first_content = response["content"][0]
            if not isinstance(first_content, dict) or "text" not in first_content:
                raise ValueError("Invalid response: 'content[0].text' missing")
            
            # Build OpenAI response
            openai_response = {
                "choices": [{
                    "finish_reason": response.get("stop_reason", "stop"),
                    "index": 0,
                    "message": {
                        "content": first_content["text"],
                        "role": response.get("role", "assistant")
                    }
                }],
                "created": int(time.time()),
                "id": response.get("id", "chatcmpl-unknown"),
                "model": response.get("model", model),
                "object": "chat.completion",
                "usage": {
                    "completion_tokens": response.get("usage", {}).get("output_tokens", 0),
                    "prompt_tokens": response.get("usage", {}).get("input_tokens", 0),
                    "total_tokens": (
                        response.get("usage", {}).get("input_tokens", 0) +
                        response.get("usage", {}).get("output_tokens", 0)
                    )
                }
            }
            
            logging.debug(f"Converted to OpenAI format: {json.dumps(openai_response, indent=2)}")
            return openai_response
            
        except Exception as e:
            logging.error(f"Error converting Claude 3.5 response: {e}", exc_info=True)
            return {
                "error": "Invalid response from Claude API",
                "details": str(e)
            }
    
    def _convert_claude37_response(self, response: Dict[str, Any], model: str) -> Dict[str, Any]:
        """Convert Claude 3.7/4/4.5 response to OpenAI format.
        
        Args:
            response: Claude 3.7+ response
            model: Model name
            
        Returns:
            OpenAI response
        """
        try:
            logging.debug(f"Converting Claude 3.7+ response: {json.dumps(response, indent=2)}")
            
            # Validate response structure
            if not isinstance(response, dict):
                raise ValueError("Response is not a dictionary")
            
            # Extract output and message
            output = response.get("output")
            if not isinstance(output, dict):
                raise ValueError("'output' field missing or invalid")
            
            message = output.get("message")
            if not isinstance(message, dict):
                raise ValueError("'output.message' field missing or invalid")
            
            # Extract content
            content_list = message.get("content")
            if not isinstance(content_list, list) or not content_list:
                raise ValueError("'output.message.content' missing or empty")
            
            # Find first text block
            content_text = None
            for block in content_list:
                if isinstance(block, dict) and block.get("type") == "text" and "text" in block:
                    content_text = block["text"]
                    break
            
            if content_text is None:
                raise ValueError("No text content found in response")
            
            # Extract usage
            usage = response.get("usage", {})
            input_tokens = usage.get("inputTokens", 0)
            output_tokens = usage.get("outputTokens", 0)
            total_tokens = usage.get("totalTokens", input_tokens + output_tokens)
            
            # Extract cache tokens if available
            prompt_tokens_details = {}
            if "cacheReadInputTokens" in usage or "cacheCreationInputTokens" in usage:
                prompt_tokens_details["cached_tokens"] = usage.get("cacheReadInputTokens", 0)
                if usage.get("cacheCreationInputTokens", 0) > 0:
                    prompt_tokens_details["cache_creation_tokens"] = usage.get("cacheCreationInputTokens", 0)
            
            # Map stop reason
            stop_reason_map = {
                "end_turn": "stop",
                "max_tokens": "length",
                "stop_sequence": "stop",
                "tool_use": "tool_calls",
            }
            claude_stop_reason = response.get("stopReason")
            finish_reason = stop_reason_map.get(claude_stop_reason, "stop")
            
            # Build OpenAI response
            openai_response = {
                "choices": [{
                    "finish_reason": finish_reason,
                    "index": 0,
                    "message": {
                        "content": content_text,
                        "role": message.get("role", "assistant")
                    }
                }],
                "created": int(time.time()),
                "id": f"chatcmpl-claude37-{int(time.time())}",
                "model": model,
                "object": "chat.completion",
                "usage": {
                    "completion_tokens": output_tokens,
                    "prompt_tokens": input_tokens,
                    "total_tokens": total_tokens
                }
            }
            
            # Add prompt_tokens_details if cache tokens present
            if prompt_tokens_details:
                openai_response["usage"]["prompt_tokens_details"] = prompt_tokens_details
            
            logging.debug(f"Converted to OpenAI format: {json.dumps(openai_response, indent=2)}")
            return openai_response
            
        except Exception as e:
            logging.error(f"Error converting Claude 3.7+ response: {e}", exc_info=True)
            logging.error(f"Problematic response: {json.dumps(response, indent=2)}")
            return {
                "object": "error",
                "message": f"Failed to convert Claude response: {str(e)}",
                "type": "proxy_conversion_error",
                "param": None,
                "code": None
            }
    
    def reverse_convert_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Claude request to OpenAI format.
        
        Args:
            payload: Claude Messages API request
            
        Returns:
            OpenAI Chat Completions request
        """
        logging.debug(f"Converting Claude request to OpenAI: {json.dumps(payload, indent=2)}")
        
        openai_messages = []
        
        # Add system message if present
        if "system" in payload and payload["system"]:
            openai_messages.append({"role": "system", "content": payload["system"]})
        
        # Add conversation messages
        openai_messages.extend(payload.get("messages", []))
        
        # Build OpenAI payload
        openai_payload = {
            "model": payload.get("model"),
            "messages": openai_messages,
        }
        
        # Map parameters
        if "max_tokens" in payload:
            openai_payload["max_completion_tokens"] = payload["max_tokens"]
        if "temperature" in payload:
            openai_payload["temperature"] = payload["temperature"]
        if "stream" in payload:
            openai_payload["stream"] = payload["stream"]
        
        # Convert tools if present
        if "tools" in payload and payload["tools"]:
            openai_tools = []
            for tool in payload["tools"]:
                openai_tool = {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool["description"],
                        "parameters": tool["input_schema"]
                    }
                }
                openai_tools.append(openai_tool)
            openai_payload["tools"] = openai_tools
        
        logging.debug(f"Converted to OpenAI format: {json.dumps(openai_payload, indent=2)}")
        return openai_payload