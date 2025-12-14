"""Base interfaces for model providers.

This module defines the abstract base classes and data structures for model providers,
following the Strategy pattern to enable extensible model support.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List


@dataclass
class ModelRequest:
    """Standardized model request structure.
    
    Attributes:
        model: Model name/identifier
        messages: List of conversation messages
        temperature: Sampling temperature (0.0-2.0)
        max_tokens: Maximum tokens to generate
        stream: Whether to stream the response
        extra_params: Additional provider-specific parameters
    """
    model: str
    messages: List[Dict[str, Any]]
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    stream: bool = False
    extra_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelResponse:
    """Standardized model response structure.
    
    Attributes:
        content: Generated text content
        model: Model that generated the response
        finish_reason: Reason for completion (stop, length, etc.)
        usage: Token usage statistics
        raw_response: Original provider response
    """
    content: str
    model: str
    finish_reason: str
    usage: Dict[str, int]
    raw_response: Dict[str, Any]


class ModelProvider(ABC):
    """Abstract base class for model providers.
    
    Implements the Strategy pattern for different model providers (Claude, Gemini, OpenAI).
    Each provider handles model detection, endpoint URL generation, and request preparation.
    """
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """Get the provider name identifier.
        
        Returns:
            Provider name (e.g., 'claude', 'gemini', 'openai')
        """
        pass
    
    @abstractmethod
    def supports_model(self, model: str) -> bool:
        """Check if this provider supports the given model.
        
        Args:
            model: Model name to check
            
        Returns:
            True if provider supports this model, False otherwise
        """
        pass
    
    @abstractmethod
    def get_endpoint_url(self, base_url: str, model: str, stream: bool) -> str:
        """Generate the API endpoint URL for this model.
        
        Args:
            base_url: Base URL from deployment configuration
            model: Model name
            stream: Whether this is a streaming request
            
        Returns:
            Complete endpoint URL
        """
        pass
    
    @abstractmethod
    def prepare_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare request payload for this provider.
        
        Note: This method does NOT perform format conversion (that's in converters/).
        It only handles provider-specific request preparation like parameter filtering.
        
        Args:
            payload: Original request payload
            
        Returns:
            Modified payload ready for the provider's API
        """
        pass


class StreamingProvider(ABC):
    """Abstract base class for streaming-capable providers.
    
    Providers that support streaming responses should implement this interface
    in addition to ModelProvider.
    """
    
    @abstractmethod
    def supports_streaming(self) -> bool:
        """Check if this provider supports streaming responses.
        
        Returns:
            True if streaming is supported, False otherwise
        """
        pass
    
    @abstractmethod
    def get_streaming_endpoint(self, base_url: str, model: str) -> str:
        """Get the streaming-specific endpoint URL.
        
        Args:
            base_url: Base URL from deployment configuration
            model: Model name
            
        Returns:
            Streaming endpoint URL
        """
        pass