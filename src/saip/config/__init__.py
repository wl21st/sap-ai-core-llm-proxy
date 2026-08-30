"""
Configuration management package for SAP AI Core LLM Proxy.

This package handles:
- Configuration dataclasses (ServiceKey, TokenInfo, SubAccountConfig, ProxyConfig)
- Configuration loading from JSON files
- Subaccount initialization and model mapping
"""

from .config_models import ServiceKey, TokenInfo, SubAccountConfig, ProxyConfig

# from .config_parser import load_proxy_config
from .global_context import ProxyGlobalContext


# Lazy load load_proxy_config to avoid circular import with utils.sdk_utils
def load_proxy_config(file_path: str) -> ProxyConfig:
    from .config_parser import load_proxy_config as _load

    return _load(file_path)


__all__ = [
    "ServiceKey",
    "TokenInfo",
    "SubAccountConfig",
    "ProxyConfig",
    "load_proxy_config",
    "ProxyGlobalContext",
]
