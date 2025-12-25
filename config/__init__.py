"""
Configuration management package for SAP AI Core LLM Proxy.

This package handles:
- Configuration dataclasses (ServiceKey, TokenInfo, SubAccountConfig, ProxyConfig)
- Configuration loading from JSON files
- Subaccount initialization and model mapping
"""

from .config_models import ServiceKey, TokenInfo, SubAccountConfig, ProxyConfig
from .config_parser import load_proxy_config

__all__ = [
    'ServiceKey',
    'TokenInfo',
    'SubAccountConfig',
    'ProxyConfig',
    'load_proxy_config',
]