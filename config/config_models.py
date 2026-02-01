"""
Configuration dataclasses for SAP AI Core LLM Proxy.

This module defines the core configuration structures used throughout the proxy.
"""

import threading
from dataclasses import dataclass, field
from logging import Logger
from typing import Optional

from utils.logging_utils import get_server_logger

logger: Logger = get_server_logger(__name__)


@dataclass
class ModelFilters:
    """Model filtering configuration with include/exclude regex patterns."""

    include: Optional[list[str]] = None
    exclude: Optional[list[str]] = None


@dataclass
class ServiceKey:
    """SAP AI Core service key credentials."""

    client_id: str
    client_secret: str
    auth_url: str
    identity_zone_id: str
    api_url: str


@dataclass
class TokenInfo:
    """Token information with caching and thread-safety."""

    token: str = ""
    expiry: float = 0
    lock: threading.Lock = field(default_factory=threading.Lock)


@dataclass
class SubAccountConfig:
    """Configuration for a single SAP AI Core subaccount."""

    name: str
    resource_group: str
    service_key_json: str
    model_to_deployment_urls: dict[str, list[str]]
    service_key: ServiceKey = field(init=False)
    token_info: TokenInfo = field(default_factory=TokenInfo)
    model_to_deployment_ids: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class ProxyConfig:
    """Main proxy configuration with multi-subaccount support."""

    subaccounts: dict[str, SubAccountConfig] = field(default_factory=dict)
    secret_authentication_tokens: list[str] = field(default_factory=list)
    port: int = 3001
    host: str = "127.0.0.1"
    model_filters: Optional[ModelFilters] = None
    # Global model to subaccount mapping for load balancing
    model_to_subaccounts: dict[str, list[str]] = field(default_factory=dict)

    def get_subaccount(self, subaccount_name: str) -> SubAccountConfig:
        return self.subaccounts[subaccount_name]
