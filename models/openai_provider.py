"""OpenAI model provider implementation.

This module implements the ModelProvider interface for OpenAI and Azure OpenAI models,
supporting GPT-4, GPT-5, o3, and o4-mini variants.
"""

import logging
from typing import Dict, Any

from .provider import ModelProvider, StreamingProvider


class OpenAIProvider(ModelProvider, StreamingProvider):
    """Provider for OpenAI and Azure OpenAI models.
    
    Supports:
    - GPT-4, GPT-4o, GPT-4.1
    - GPT-5
    - o3, o3-mini, o4-mini (reasoning models)
    
    Features:
    - API version selection based on model
    - Parameter filtering for o3-mini (removes temperature)
    - Streaming support
    """
    
    def __init__(self):
        """Initialize OpenAI provider."""
        self._logger = logging.getLogger(__name__)
    
    def get_provider_name(self) -> str:
        """Get provider name.
        
        Returns:
            'openai'
        """
        return "openai"
    
    def supports_model(self, model: str) -> bool:
        """Check if this is an OpenAI model.
        
        This is the default/fallback provider, so it accepts any model
        that isn't explicitly handled by Claude or Gemini providers.
        
        Args:
            model: Model name to check
            
        Returns:
            True (accepts all models as fallback)
        """
        # OpenAI provider acts as fallback for non-Claude, non-Gemini models
        # Specific model detection can be added here if needed
        return True
    
    def get_endpoint_url(self, base_url: str, model: str, stream: bool) -> str:
        """Generate endpoint URL for OpenAI model.
        
        OpenAI uses /chat/completions with api-version query parameter.
        API version depends on model type.
        
        Args:
            base_url: Base URL from deployment configuration
            model: Model name
            stream: Whether this is a streaming request (not used for URL)
            
        Returns:
            Complete endpoint URL with API version
        """
        # Determine API version based on model
        api_version = self._get_api_version(model)
        
        endpoint_url = f"{base_url.rstrip('/')}/chat/completions?api-version={api_version}"
        self._logger.debug(
            f"OpenAI endpoint for model '{model}' (api_version={api_version}): {endpoint_url}"
        )
        
        return endpoint_url
    
    def prepare_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare request payload for OpenAI API.
        
        Handles special cases like o3-mini which doesn't support temperature parameter.
        
        Args:
            payload: Original request payload
            
        Returns:
            Payload ready for OpenAI API
        """
        model = payload.get("model", "")
        
        # o3-mini doesn't support temperature parameter
        if self._is_o3_mini_model(model):
            modified_payload = payload.copy()
            if 'temperature' in modified_payload:
                self._logger.info(f"Removing 'temperature' parameter for o3-mini model")
                del modified_payload['temperature']
            return modified_payload
        
        # For other models, return payload unchanged
        return payload
    
    def supports_streaming(self) -> bool:
        """Check if OpenAI supports streaming.
        
        Returns:
            True (OpenAI supports streaming)
        """
        return True
    
    def get_streaming_endpoint(self, base_url: str, model: str) -> str:
        """Get streaming endpoint for OpenAI.
        
        OpenAI uses the same endpoint for streaming and non-streaming,
        controlled by the 'stream' parameter in the request body.
        
        Args:
            base_url: Base URL from deployment configuration
            model: Model name
            
        Returns:
            Streaming endpoint URL (same as non-streaming)
        """
        return self.get_endpoint_url(base_url, model, stream=True)
    
    def _get_api_version(self, model: str) -> str:
        """Determine API version based on model.
        
        Args:
            model: Model name
            
        Returns:
            API version string
        """
        # o3, o4-mini, o3-mini use newer API version
        if any(m in model for m in ["o3", "o4-mini", "o3-mini"]):
            return "2024-12-01-preview"
        
        # Default API version for other models
        return "2023-05-15"
    
    def _is_o3_mini_model(self, model: str) -> bool:
        """Check if model is o3-mini.
        
        Args:
            model: Model name
            
        Returns:
            True if o3-mini model, False otherwise
        """
        return "o3-mini" in model or "o3mini" in model
    
    def is_reasoning_model(self, model: str) -> bool:
        """Check if model is a reasoning model (o3, o4-mini).
        
        Args:
            model: Model name
            
        Returns:
            True if reasoning model, False otherwise
        """
        return any(m in model for m in ["o3", "o4-mini", "o3-mini"])