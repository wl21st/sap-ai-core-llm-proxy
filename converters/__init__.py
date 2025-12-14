"""Format conversion module for multi-model proxy.

This module provides converters for transforming requests and responses between
different AI model formats (OpenAI, Claude, Gemini, Bedrock).

Key Components:
- Base converter interfaces (Converter, StreamingConverter)
- Factory for converter selection (ConverterFactory)
- Model-specific converters (ClaudeConverter, GeminiConverter, etc.)
- Streaming chunk converters

Usage:
    from converters import ConverterFactory
    
    # Get converter for format conversion
    converter = ConverterFactory.get_converter('openai', 'claude')
    claude_payload = converter.convert_request(openai_payload)
    
    # Get streaming converter
    streaming = ConverterFactory.get_streaming_converter('claude')
    sse_chunk = streaming.convert_chunk(claude_chunk, model_name)
"""

from converters.base import Converter, StreamingConverter
from converters.factory import ConverterFactory
from converters.claude_converter import ClaudeConverter
from converters.gemini_converter import GeminiConverter
from converters.bedrock_converter import BedrockConverter
from converters.streaming_converter import (
    ClaudeStreamingConverter,
    GeminiStreamingConverter,
    OpenAIStreamingConverter
)

__all__ = [
    'Converter',
    'StreamingConverter',
    'ConverterFactory',
    'ClaudeConverter',
    'GeminiConverter',
    'BedrockConverter',
    'ClaudeStreamingConverter',
    'GeminiStreamingConverter',
    'OpenAIStreamingConverter',
]

__version__ = '1.0.0'