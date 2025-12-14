"""Bedrock format converter for Claude→Bedrock conversions.

This module handles conversion from Claude Messages API format to
AWS Bedrock Claude format, removing unsupported fields and ensuring
compatibility with Bedrock's API requirements.
"""

import logging
import json
from typing import Dict, Any

from converters.base import Converter


class BedrockConverter(Converter):
    """Converter for Claude → Bedrock format transformations.
    
    Handles:
    - Removing cache_control fields (not supported by Bedrock)
    - Removing input_examples from tools (not supported)
    - Ensuring anthropic_version is set correctly
    - Converting content to proper block format
    
    This is a one-way converter as Bedrock responses are already
    in Claude format.
    """
    
    def get_source_format(self) -> str:
        """Get source format name."""
        return "claude"
    
    def get_target_format(self) -> str:
        """Get target format name."""
        return "bedrock"
    
    def convert_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Claude request to Bedrock-compatible format.
        
        Removes unsupported fields and ensures proper formatting for
        AWS Bedrock Claude API.
        
        Args:
            payload: Claude Messages API request payload
            
        Returns:
            Bedrock-compatible Claude request payload
        """
        logging.debug(f"Converting Claude to Bedrock: {json.dumps(payload, indent=2)}")
        
        bedrock_payload = {}
        
        # Copy basic fields
        for field in ["model", "max_tokens", "temperature", "top_p", "top_k", "stop_sequences"]:
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
                                k: v for k, v in content_item.items() 
                                if k != "cache_control"
                            }
                            cleaned_content.append(cleaned_item)
                        else:
                            cleaned_content.append(content_item)
                    cleaned_message["content"] = cleaned_content
                else:
                    # Convert string content to block format
                    cleaned_message["content"] = [
                        {"type": "text", "text": message["content"]}
                    ]
                
                cleaned_messages.append(cleaned_message)
            bedrock_payload["messages"] = cleaned_messages
        
        # Handle tools conversion if present
        if "tools" in payload and payload["tools"]:
            cleaned_tools = []
            removed_count = 0
            
            for tool in payload["tools"]:
                if isinstance(tool, dict):
                    cleaned_tool = tool.copy()
                    
                    # Remove top-level input_examples
                    if "input_examples" in cleaned_tool:
                        cleaned_tool.pop("input_examples")
                        removed_count += 1
                    
                    # Remove nested custom.input_examples
                    custom = cleaned_tool.get("custom")
                    if isinstance(custom, dict) and "input_examples" in custom:
                        custom.pop("input_examples")
                        removed_count += 1
                    
                    cleaned_tools.append(cleaned_tool)
            
            bedrock_payload["tools"] = cleaned_tools
            
            if removed_count > 0:
                logging.debug(f"Removed {removed_count} input_examples from tools")
        
        # Set anthropic_version if not present
        if "anthropic_version" not in bedrock_payload:
            bedrock_payload["anthropic_version"] = "bedrock-2023-05-31"
        
        logging.debug(f"Converted to Bedrock format: {json.dumps(bedrock_payload, indent=2)}")
        return bedrock_payload
    
    def convert_response(self, response: Dict[str, Any], model: str) -> Dict[str, Any]:
        """Convert Bedrock response to Claude format.
        
        Note: Bedrock responses are already in Claude format, so this
        is essentially a pass-through with validation.
        
        Args:
            response: Bedrock Claude response
            model: Model name
            
        Returns:
            Claude Messages API response (unchanged)
        """
        # Bedrock responses are already in Claude format
        logging.debug("Bedrock response is already in Claude format")
        return response