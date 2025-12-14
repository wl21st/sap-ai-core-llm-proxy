"""Gemini model provider implementation.

This module implements the ModelProvider interface for Google Gemini models,
supporting Gemini 1.5, 2.5, Pro, and Flash variants.
"""

import logging
from typing import Dict, Any

from .provider import ModelProvider, StreamingProvider
from .detector import ModelDetector


class GeminiProvider(ModelProvider, StreamingProvider):
    """Provider for Google Gemini models.
    
    Supports:
    - Gemini 1.5 Pro/Flash
    - Gemini 2.5 Pro/Flash
    - Generic gemini-pro, gemini-flash
    
    Features:
    - Automatic endpoint generation with model name
    - Streaming support with :streamGenerateContent endpoint
    - Model name extraction for endpoint construction
    """
    
    def __init__(self):
        """Initialize Gemini provider."""
        self._logger = logging.getLogger(__name__)
        self._detector = ModelDetector()
    
    def get_provider_name(self) -> str:
        """Get provider name.
        
        Returns:
            'gemini'
        """
        return "gemini"
    
    def supports_model(self, model: str) -> bool:
        """Check if this is a Gemini model.
        
        Args:
            model: Model name to check
            
        Returns:
            True if Gemini model, False otherwise
        """
        return self._detector.is_gemini_model(model)
    
    def get_endpoint_url(self, base_url: str, model: str, stream: bool) -> str:
        """Generate endpoint URL for Gemini model.
        
        Gemini uses /models/{model}:generateContent or :streamGenerateContent
        
        Args:
            base_url: Base URL from deployment configuration
            model: Model name
            stream: Whether this is a streaming request
            
        Returns:
            Complete endpoint URL
        """
        # Extract model name for endpoint (remove any version suffix after colon)
        model_endpoint_name = self._extract_model_endpoint_name(model)
        
        # Select endpoint based on streaming
        if stream:
            endpoint_path = f"/models/{model_endpoint_name}:streamGenerateContent"
        else:
            endpoint_path = f"/models/{model_endpoint_name}:generateContent"
        
        endpoint_url = f"{base_url.rstrip('/')}{endpoint_path}"
        self._logger.debug(
            f"Gemini endpoint for model '{model}' (stream={stream}): {endpoint_url}"
        )
        
        return endpoint_url
    
    def prepare_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare request payload for Gemini API.
        
        Note: This does NOT perform format conversion (that's in converters/).
        It only handles Gemini-specific parameter filtering if needed.
        
        Args:
            payload: Original request payload
            
        Returns:
            Payload ready for Gemini API (currently unchanged)
        """
        # For now, Gemini doesn't need special parameter filtering
        # The conversion is handled by converter functions
        return payload
    
    def supports_streaming(self) -> bool:
        """Check if Gemini supports streaming.
        
        Returns:
            True (Gemini supports streaming)
        """
        return True
    
    def get_streaming_endpoint(self, base_url: str, model: str) -> str:
        """Get streaming endpoint for Gemini.
        
        Args:
            base_url: Base URL from deployment configuration
            model: Model name
            
        Returns:
            Streaming endpoint URL
        """
        return self.get_endpoint_url(base_url, model, stream=True)
    
    def _extract_model_endpoint_name(self, model: str) -> str:
        """Extract model name for endpoint construction.
        
        Removes version suffixes after colon if present.
        For example: "gemini-2.5-pro:latest" -> "gemini-2.5-pro"
        
        Args:
            model: Full model name
            
        Returns:
            Model name for endpoint
        """
        if ":" in model:
            return model.split(":")[0]
        return model
    
    def get_model_variant(self, model: str) -> str:
        """Get Gemini model variant (pro or flash).
        
        Args:
            model: Model name
            
        Returns:
            Variant string ("pro", "flash", or "unknown")
        """
        model_lower = model.lower()
        if "flash" in model_lower:
            return "flash"
        elif "pro" in model_lower:
            return "pro"
        return "unknown"
    
    def get_model_version(self, model: str) -> str:
        """Get Gemini model version.
        
        Args:
            model: Model name
            
        Returns:
            Version string (e.g., "1.5", "2.5")
        """
        version = self._detector.get_model_version(model)
        return version if version else "unknown"