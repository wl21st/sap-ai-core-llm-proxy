"""Claude model provider implementation.

This module implements the ModelProvider interface for Anthropic Claude models,
supporting Claude 3.5, 3.7, 4, and 4.5 variants.
"""

import logging
from typing import Dict, Any

from .provider import ModelProvider, StreamingProvider
from .detector import ModelDetector


class ClaudeProvider(ModelProvider, StreamingProvider):
    """Provider for Anthropic Claude models.
    
    Supports:
    - Claude 3.5 Sonnet (uses /invoke endpoint)
    - Claude 3.7 Sonnet (uses /converse endpoint)
    - Claude 4 Sonnet/Opus (uses /converse endpoint)
    - Claude 4.5 Sonnet (uses /converse endpoint)
    
    Features:
    - Automatic endpoint selection based on model version
    - Model name normalization (handles anthropic-- prefix)
    - Streaming support with version-specific endpoints
    """
    
    def __init__(self):
        """Initialize Claude provider."""
        self._logger = logging.getLogger(__name__)
        self._detector = ModelDetector()
    
    def get_provider_name(self) -> str:
        """Get provider name.
        
        Returns:
            'claude'
        """
        return "claude"
    
    def supports_model(self, model: str) -> bool:
        """Check if this is a Claude model.
        
        Args:
            model: Model name to check
            
        Returns:
            True if Claude model, False otherwise
        """
        return self._detector.is_claude_model(model)
    
    def get_endpoint_url(self, base_url: str, model: str, stream: bool) -> str:
        """Generate endpoint URL for Claude model.
        
        Claude 3.5 uses /invoke or /invoke-with-response-stream
        Claude 3.7/4/4.5 use /converse or /converse-stream
        
        Args:
            base_url: Base URL from deployment configuration
            model: Model name
            stream: Whether this is a streaming request
            
        Returns:
            Complete endpoint URL
        """
        # Determine if this is Claude 3.7 or newer
        is_new_version = self._detector.is_claude_37_or_4(model)
        
        # Select endpoint based on version and streaming
        if stream:
            if is_new_version:
                endpoint_path = "/converse-stream"
            else:
                endpoint_path = "/invoke-with-response-stream"
        else:
            if is_new_version:
                endpoint_path = "/converse"
            else:
                endpoint_path = "/invoke"
        
        endpoint_url = f"{base_url.rstrip('/')}{endpoint_path}"
        self._logger.debug(
            f"Claude endpoint for model '{model}' (stream={stream}): {endpoint_url}"
        )
        
        return endpoint_url
    
    def prepare_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare request payload for Claude API.
        
        Note: This does NOT perform format conversion (that's in converters/).
        It only handles Claude-specific parameter filtering if needed.
        
        Args:
            payload: Original request payload
            
        Returns:
            Payload ready for Claude API (currently unchanged)
        """
        # For now, Claude doesn't need special parameter filtering
        # The conversion is handled by converter functions
        return payload
    
    def supports_streaming(self) -> bool:
        """Check if Claude supports streaming.
        
        Returns:
            True (Claude supports streaming)
        """
        return True
    
    def get_streaming_endpoint(self, base_url: str, model: str) -> str:
        """Get streaming endpoint for Claude.
        
        Args:
            base_url: Base URL from deployment configuration
            model: Model name
            
        Returns:
            Streaming endpoint URL
        """
        return self.get_endpoint_url(base_url, model, stream=True)
    
    def normalize_model_name(self, model: str) -> str:
        """Normalize Claude model name.
        
        Removes common prefixes like 'anthropic--' for consistent handling.
        
        Args:
            model: Original model name
            
        Returns:
            Normalized model name
        """
        # Remove anthropic-- prefix if present
        if model.startswith("anthropic--"):
            return model.replace("anthropic--", "")
        return model
    
    def get_model_version(self, model: str) -> str:
        """Get Claude model version.
        
        Args:
            model: Model name
            
        Returns:
            Version string (e.g., "3.5", "3.7", "4", "4.5")
        """
        version = self._detector.get_model_version(model)
        return version if version else "unknown"