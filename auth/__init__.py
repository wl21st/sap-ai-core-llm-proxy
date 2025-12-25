"""
Authentication module for SAP AI Core LLM Proxy.

This module provides authentication-related functionality including:
- Token management with caching and thread-safety
- Request validation against configured tokens
"""

from .token_manager import TokenManager
from .request_validator import RequestValidator

__all__ = [
    'TokenManager',
    'RequestValidator',
]