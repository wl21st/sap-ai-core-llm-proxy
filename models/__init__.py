"""Model provider abstraction module.

This module provides a clean abstraction for different AI model providers
(Claude, Gemini, OpenAI) following the Strategy pattern.

Usage:
    from models import ProviderRegistry, ClaudeProvider, GeminiProvider, OpenAIProvider
    
    # Initialize registry
    registry = ProviderRegistry()
    registry.register(ClaudeProvider())
    registry.register(GeminiProvider())
    registry.register(OpenAIProvider())
    
    # Get provider for a model
    provider = registry.get_provider("claude-4.5-sonnet")
    endpoint = provider.get_endpoint_url(base_url, model, stream=False)
"""

from .detector import ModelDetector, is_claude_model, is_gemini_model, is_claude_37_or_4
from .provider import (
    ModelProvider,
    StreamingProvider,
    ModelRequest,
    ModelResponse,
)
from .claude_provider import ClaudeProvider
from .gemini_provider import GeminiProvider
from .openai_provider import OpenAIProvider
from .registry import ProviderRegistry, get_global_registry

__all__ = [
    # Detector
    "ModelDetector",
    "is_claude_model",
    "is_gemini_model",
    "is_claude_37_or_4",
    # Provider interfaces
    "ModelProvider",
    "StreamingProvider",
    "ModelRequest",
    "ModelResponse",
    # Provider implementations
    "ClaudeProvider",
    "GeminiProvider",
    "OpenAIProvider",
    # Registry
    "ProviderRegistry",
    "get_global_registry",
]

__version__ = "1.0.0"