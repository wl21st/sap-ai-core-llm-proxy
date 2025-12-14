"""Gemini format converter for OpenAI ↔ Gemini conversions.

This module handles bidirectional conversion between OpenAI Chat Completions
format and Google Gemini generateContent API format.
"""

import logging
import time
import json
import random
from typing import Dict, Any

from converters.base import BidirectionalConverter


class GeminiConverter(BidirectionalConverter):
    """Converter for OpenAI ↔ Gemini format transformations.
    
    Supports:
    - OpenAI → Gemini (generateContent format)
    - Gemini → OpenAI (response conversion)
    
    Handles both single-message and multi-message conversations,
    with proper role mapping (user/assistant → user/model).
    """
    
    def get_source_format(self) -> str:
        """Get source format name."""
        return "openai"
    
    def get_target_format(self) -> str:
        """Get target format name."""
        return "gemini"
    
    def convert_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Convert OpenAI request to Gemini format.
        
        Args:
            payload: OpenAI Chat Completions request payload
            
        Returns:
            Gemini generateContent request payload
            
        Raises:
            ValueError: If payload is invalid
        """
        logging.debug(f"Converting OpenAI to Gemini: {json.dumps(payload, indent=2)}")
        
        # Extract system message if present
        system_message = ""
        messages = payload.get("messages", []).copy()
        
        if messages and messages[0].get("role") == "system":
            system_message = messages.pop(0).get("content", "")
        
        # Build generation config
        generation_config = {}
        
        if "max_tokens" in payload:
            try:
                generation_config["maxOutputTokens"] = int(payload["max_tokens"])
            except (ValueError, TypeError):
                logging.warning(f"Invalid max_tokens: {payload['max_tokens']}")
        
        if "temperature" in payload:
            try:
                generation_config["temperature"] = float(payload["temperature"])
            except (ValueError, TypeError):
                logging.warning(f"Invalid temperature: {payload['temperature']}")
        
        if "top_p" in payload:
            try:
                generation_config["topP"] = float(payload["top_p"])
            except (ValueError, TypeError):
                logging.warning(f"Invalid top_p: {payload['top_p']}")
        
        # Convert messages to Gemini format
        if len(messages) == 1 and messages[0].get("role") == "user":
            # Single user message case - use simple structure
            user_content = self._extract_text_content(messages[0].get("content", ""))
            
            # Prepend system message if present
            if system_message:
                user_content = system_message + "\n\n" + user_content
            
            gemini_contents = {
                "role": "user",
                "parts": {"text": user_content}
            }
        else:
            # Multiple messages case - use array format
            gemini_contents = []
            
            # Add system message as first user message if present
            if system_message:
                gemini_contents.append({
                    "role": "user",
                    "parts": {"text": system_message}
                })
            
            # Process remaining messages
            for msg in messages:
                role = msg.get("role")
                content = self._extract_text_content(msg.get("content", ""))
                
                # Map OpenAI roles to Gemini roles
                if role == "user":
                    gemini_role = "user"
                elif role == "assistant":
                    gemini_role = "model"
                else:
                    logging.warning(f"Skipping unsupported role: {role}")
                    continue
                
                if content:
                    # Check if we can merge with previous message (same role)
                    if gemini_contents and gemini_contents[-1]["role"] == gemini_role:
                        # Merge with previous message
                        if isinstance(gemini_contents[-1]["parts"], dict):
                            gemini_contents[-1]["parts"]["text"] += "\n\n" + content
                        else:
                            gemini_contents[-1]["parts"] = {
                                "text": gemini_contents[-1]["parts"]["text"] + "\n\n" + content
                            }
                    else:
                        # Add new message
                        gemini_contents.append({
                            "role": gemini_role,
                            "parts": {"text": content}
                        })
        
        # Build safety settings
        safety_settings = {
            "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
            "threshold": "BLOCK_LOW_AND_ABOVE"
        }
        
        # Construct final payload
        gemini_payload = {"contents": gemini_contents}
        
        if generation_config:
            gemini_payload["generation_config"] = generation_config
        
        gemini_payload["safety_settings"] = safety_settings
        
        logging.debug(f"Converted to Gemini format: {json.dumps(gemini_payload, indent=2)}")
        return gemini_payload
    
    def _extract_text_content(self, content: Any) -> str:
        """Extract text from content (string or list of blocks).
        
        Args:
            content: Content to extract text from
            
        Returns:
            Extracted text string
        """
        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            # Extract text from content blocks
            text_parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
                elif isinstance(block, str):
                    text_parts.append(block)
            return " ".join(text_parts)
        else:
            return str(content)
    
    def convert_response(self, response: Dict[str, Any], model: str) -> Dict[str, Any]:
        """Convert Gemini response to OpenAI format.
        
        Args:
            response: Gemini generateContent response
            model: Model name
            
        Returns:
            OpenAI Chat Completions response
            
        Raises:
            ValueError: If response is invalid
        """
        try:
            logging.debug(f"Converting Gemini response: {json.dumps(response, indent=2)}")
            
            # Validate response structure
            if not isinstance(response, dict):
                raise ValueError("Response is not a dictionary")
            
            # Extract candidates
            candidates = response.get("candidates", [])
            if not candidates:
                raise ValueError("No candidates found in response")
            
            first_candidate = candidates[0]
            if not isinstance(first_candidate, dict):
                raise ValueError("Candidate is not a dictionary")
            
            # Extract content
            content = first_candidate.get("content", {})
            if not isinstance(content, dict):
                raise ValueError("Content is not a dictionary")
            
            # Extract parts
            parts = content.get("parts", [])
            if not parts:
                raise ValueError("No parts found in content")
            
            first_part = parts[0]
            if not isinstance(first_part, dict) or "text" not in first_part:
                raise ValueError("No text found in first part")
            
            content_text = first_part["text"]
            
            # Map finish reason
            finish_reason_map = {
                "STOP": "stop",
                "MAX_TOKENS": "length",
                "SAFETY": "content_filter",
                "RECITATION": "content_filter",
                "OTHER": "stop"
            }
            gemini_finish_reason = first_candidate.get("finishReason", "STOP")
            finish_reason = finish_reason_map.get(gemini_finish_reason, "stop")
            
            # Extract usage
            usage_metadata = response.get("usageMetadata", {})
            prompt_tokens = usage_metadata.get("promptTokenCount", 0)
            completion_tokens = usage_metadata.get("candidatesTokenCount", 0)
            total_tokens = usage_metadata.get("totalTokenCount", prompt_tokens + completion_tokens)
            
            # Build OpenAI response
            openai_response = {
                "choices": [{
                    "finish_reason": finish_reason,
                    "index": 0,
                    "message": {
                        "content": content_text,
                        "role": "assistant"
                    }
                }],
                "created": int(time.time()),
                "id": f"chatcmpl-gemini-{random.randint(10000, 99999)}",
                "model": model,
                "object": "chat.completion",
                "usage": {
                    "completion_tokens": completion_tokens,
                    "prompt_tokens": prompt_tokens,
                    "total_tokens": total_tokens
                }
            }
            
            logging.debug(f"Converted to OpenAI format: {json.dumps(openai_response, indent=2)}")
            return openai_response
            
        except Exception as e:
            logging.error(f"Error converting Gemini response: {e}", exc_info=True)
            logging.error(f"Problematic response: {json.dumps(response, indent=2)}")
            return {
                "object": "error",
                "message": f"Failed to convert Gemini response: {str(e)}",
                "type": "proxy_conversion_error",
                "param": None,
                "code": None
            }
    
    def reverse_convert_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Gemini request to OpenAI format.
        
        Note: This is a simplified conversion as Gemini format doesn't
        include all OpenAI parameters.
        
        Args:
            payload: Gemini generateContent request
            
        Returns:
            OpenAI Chat Completions request
        """
        logging.debug(f"Converting Gemini to OpenAI: {json.dumps(payload, indent=2)}")
        
        openai_messages = []
        contents = payload.get("contents", [])
        
        # Handle both single content object and array
        if isinstance(contents, dict):
            contents = [contents]
        
        for content in contents:
            role = "user" if content.get("role") == "user" else "assistant"
            parts = content.get("parts", {})
            
            if isinstance(parts, dict):
                text = parts.get("text", "")
            elif isinstance(parts, list):
                text = " ".join(p.get("text", "") for p in parts if isinstance(p, dict))
            else:
                text = str(parts)
            
            if text:
                openai_messages.append({
                    "role": role,
                    "content": text
                })
        
        # Build OpenAI payload
        openai_payload = {"messages": openai_messages}
        
        # Map generation config if present
        gen_config = payload.get("generation_config", {})
        if "maxOutputTokens" in gen_config:
            openai_payload["max_tokens"] = gen_config["maxOutputTokens"]
        if "temperature" in gen_config:
            openai_payload["temperature"] = gen_config["temperature"]
        if "topP" in gen_config:
            openai_payload["top_p"] = gen_config["topP"]
        
        logging.debug(f"Converted to OpenAI format: {json.dumps(openai_payload, indent=2)}")
        return openai_payload