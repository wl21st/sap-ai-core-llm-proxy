"""Base interfaces for format converters.

This module defines the abstract base classes and protocols for all converters
in the system, following the Strategy pattern for different model providers.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class ConversionResult:
    """Result of a conversion operation.
    
    Attributes:
        payload: The converted payload
        metadata: Optional metadata about the conversion
        warnings: List of warnings encountered during conversion
    """
    payload: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None
    warnings: Optional[list[str]] = None


class Converter(ABC):
    """Abstract base class for request/response converters.
    
    Implements the Strategy pattern for different model format conversions.
    Each converter handles bidirectional conversion between two formats.
    """
    
    @abstractmethod
    def convert_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Convert request payload from source format to target format.
        
        Args:
            payload: Source format request payload
            
        Returns:
            Target format request payload
            
        Raises:
            ValueError: If payload is invalid or conversion fails
        """
        pass
    
    @abstractmethod
    def convert_response(self, response: Dict[str, Any], model: str) -> Dict[str, Any]:
        """Convert response payload from target format to source format.
        
        Args:
            response: Target format response payload
            model: Model name for context
            
        Returns:
            Source format response payload
            
        Raises:
            ValueError: If response is invalid or conversion fails
        """
        pass
    
    @abstractmethod
    def get_source_format(self) -> str:
        """Get the source format name (e.g., 'openai', 'claude')."""
        pass
    
    @abstractmethod
    def get_target_format(self) -> str:
        """Get the target format name (e.g., 'claude', 'gemini')."""
        pass


class StreamingConverter(ABC):
    """Abstract base class for streaming chunk converters.
    
    Handles conversion of streaming response chunks to SSE format.
    """
    
    @abstractmethod
    def convert_chunk(self, chunk: Any, model_name: str) -> Optional[str]:
        """Convert a streaming chunk to SSE format.
        
        Args:
            chunk: Raw chunk from provider (string or dict)
            model_name: Model name for context
            
        Returns:
            SSE-formatted string or None if chunk should be skipped
            
        Raises:
            ValueError: If chunk is invalid
        """
        pass
    
    @abstractmethod
    def extract_usage_from_metadata(self, metadata: Dict[str, Any]) -> Dict[str, int]:
        """Extract token usage from metadata chunk.
        
        Args:
            metaMetadata chunk containing usage information
            
        Returns:
            Dictionary with 'prompt_tokens', 'completion_tokens', 'total_tokens'
        """
        pass
    
    @abstractmethod
    def get_format_name(self) -> str:
        """Get the format name this converter handles (e.g., 'claude', 'gemini')."""
        pass


class BidirectionalConverter(Converter):
    """Base class for converters that support bidirectional conversion.
    
    Provides helper methods for converters that can convert in both directions
    (e.g., OpenAI ↔ Claude).
    """
    
    def supports_reverse_conversion(self) -> bool:
        """Check if this converter supports reverse conversion.
        
        Returns:
            True if reverse conversion is supported
        """
        return True
    
    def reverse_convert_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Convert request in reverse direction (target → source).
        
        Args:
            payload: Target format request payload
            
        Returns:
            Source format request payload
        """
        raise NotImplementedError("Reverse conversion not implemented")
    
    def reverse_convert_response(self, response: Dict[str, Any], model: str) -> Dict[str, Any]:
        """Convert response in reverse direction (source → target).
        
        Args:
            response: Source format response payload
            model: Model name for context
            
        Returns:
            Target format response payload
        """
        raise NotImplementedError("Reverse conversion not implemented")