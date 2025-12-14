"""Converter factory for model format conversions.

This module implements the Factory pattern for creating appropriate converters
based on source and target formats.
"""

from typing import Dict, Type, Optional
import logging
import threading

from converters.base import Converter, StreamingConverter


class ConverterFactory:
    """Factory for creating appropriate converters based on model types.
    
    Implements the Factory pattern with thread-safe registration and lookup.
    Converters are registered at module import time and can be retrieved
    based on source/target format pairs.
    """
    
    _converters: Dict[str, Type[Converter]] = {}
    _streaming_converters: Dict[str, Type[StreamingConverter]] = {}
    _lock = threading.Lock()
    
    @classmethod
    def register_converter(cls, source_format: str, target_format: str, 
                          converter_class: Type[Converter]) -> None:
        """Register a converter for a source/target format pair.
        
        Args:
            source_format: Source format identifier (e.g., 'openai', 'claude')
            target_format: Target format identifier (e.g., 'claude', 'gemini')
            converter_class: Converter class to register
            
        Example:
            ConverterFactory.register_converter('openai', 'claude', ClaudeConverter)
        """
        with cls._lock:
            converter_key = f"{source_format}_to_{target_format}"
            cls._converters[converter_key] = converter_class
            logging.debug(f"Registered converter: {converter_key} -> {converter_class.__name__}")
    
    @classmethod
    def register_streaming_converter(cls, format_name: str, 
                                     converter_class: Type[StreamingConverter]) -> None:
        """Register a streaming converter for a format.
        
        Args:
            format_name: Format identifier (e.g., 'claude', 'gemini')
            converter_class: StreamingConverter class to register
            
        Example:
            ConverterFactory.register_streaming_converter('claude', ClaudeStreamingConverter)
        """
        with cls._lock:
            cls._streaming_converters[format_name] = converter_class
            logging.debug(f"Registered streaming converter: {format_name} -> {converter_class.__name__}")
    
    @classmethod
    def get_converter(cls, source_format: str, target_format: str) -> Converter:
        """Get appropriate converter for format conversion.
        
        Args:
            source_format: Source format (e.g., 'openai', 'claude')
            target_format: Target format (e.g., 'claude', 'gemini')
            
        Returns:
            Converter instance for the format pair
            
        Raises:
            ValueError: If no converter found for the format pair
            
        Example:
            converter = ConverterFactory.get_converter('openai', 'claude')
            claude_payload = converter.convert_request(openai_payload)
        """
        converter_key = f"{source_format}_to_{target_format}"
        
        with cls._lock:
            if converter_key not in cls._converters:
                # Try to find a bidirectional converter in reverse
                reverse_key = f"{target_format}_to_{source_format}"
                if reverse_key in cls._converters:
                    logging.debug(f"Using reverse converter for {converter_key}")
                    converter_class = cls._converters[reverse_key]
                    return converter_class()
                
                raise ValueError(
                    f"No converter found for {source_format} -> {target_format}. "
                    f"Available converters: {', '.join(cls._converters.keys())}"
                )
            
            converter_class = cls._converters[converter_key]
            return converter_class()
    
    @classmethod
    def get_streaming_converter(cls, format_name: str) -> StreamingConverter:
        """Get streaming converter for a format.
        
        Args:
            format_name: Format identifier (e.g., 'claude', 'gemini')
            
        Returns:
            StreamingConverter instance for the format
            
        Raises:
            ValueError: If no streaming converter found for the format
            
        Example:
            converter = ConverterFactory.get_streaming_converter('claude')
            sse_chunk = converter.convert_chunk(claude_chunk, model_name)
        """
        with cls._lock:
            if format_name not in cls._streaming_converters:
                raise ValueError(
                    f"No streaming converter found for format '{format_name}'. "
                    f"Available formats: {', '.join(cls._streaming_converters.keys())}"
                )
            
            converter_class = cls._streaming_converters[format_name]
            return converter_class()
    
    @classmethod
    def list_converters(cls) -> Dict[str, str]:
        """List all registered converters.
        
        Returns:
            Dictionary mapping converter keys to class names
        """
        with cls._lock:
            return {
                key: converter_class.__name__ 
                for key, converter_class in cls._converters.items()
            }
    
    @classmethod
    def list_streaming_converters(cls) -> Dict[str, str]:
        """List all registered streaming converters.
        
        Returns:
            Dictionary mapping format names to class names
        """
        with cls._lock:
            return {
                format_name: converter_class.__name__
                for format_name, converter_class in cls._streaming_converters.items()
            }
    
    @classmethod
    def clear_all(cls) -> None:
        """Clear all registered converters.
        
        This is primarily useful for testing purposes.
        """
        with cls._lock:
            cls._converters.clear()
            cls._streaming_converters.clear()
            logging.debug("Cleared all registered converters")
    
    @classmethod
    def has_converter(cls, source_format: str, target_format: str) -> bool:
        """Check if a converter exists for the format pair.
        
        Args:
            source_format: Source format identifier
            target_format: Target format identifier
            
        Returns:
            True if converter exists, False otherwise
        """
        converter_key = f"{source_format}_to_{target_format}"
        reverse_key = f"{target_format}_to_{source_format}"
        
        with cls._lock:
            return converter_key in cls._converters or reverse_key in cls._converters
    
    @classmethod
    def has_streaming_converter(cls, format_name: str) -> bool:
        """Check if a streaming converter exists for the format.
        
        Args:
            format_name: Format identifier
            
        Returns:
            True if streaming converter exists, False otherwise
        """
        with cls._lock:
            return format_name in cls._streaming_converters