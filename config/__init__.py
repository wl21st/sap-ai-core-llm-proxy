"""
Configuration management package for SAP AI Core LLM Proxy.

This package handles:
- Configuration dataclasses (ServiceKey, TokenInfo, SubAccountConfig, ProxyConfig)
- Configuration loading from JSON files
- Subaccount initialization and model mapping
"""

from .models import ServiceKey, TokenInfo, SubAccountConfig, ProxyConfig
from .loader import load_config

__all__ = [
    'ServiceKey',
    'TokenInfo',
    'SubAccountConfig',
    'ProxyConfig',
    'load_config',
]