"""
Configuration dataclasses for SAP AI Core LLM Proxy.

This module defines the core configuration structures used throughout the proxy.
"""

import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class ServiceKey:
    """SAP AI Core service key credentials."""

    clientid: str
    clientsecret: str
    url: str
    identityzoneid: str


@dataclass
class TokenInfo:
    """Token information with caching and thread-safety."""

    token: Optional[str] = None
    expiry: float = 0
    lock: threading.Lock = field(default_factory=threading.Lock)


@dataclass
class SubAccountConfig:
    """Configuration for a single SAP AI Core subaccount."""

    name: str
    resource_group: str
    service_key_json: str
    deployment_models: Dict[str, List[str]]
    service_key: Optional[ServiceKey] = None
    token_info: TokenInfo = field(default_factory=TokenInfo)
    normalized_models: Dict[str, List[str]] = field(default_factory=dict)

    def load_service_key(self):
        """Load service key from file.

        This method imports load_config to avoid circular dependencies.
        """
        from .loader import load_config

        key_data = load_config(self.service_key_json)
        self.service_key = ServiceKey(
            clientid=key_data.get("clientid"),
            clientsecret=key_data.get("clientsecret"),
            url=key_data.get("url"),
            identityzoneid=key_data.get("identityzoneid"),
        )

    def normalize_model_names(self):
        """Normalize model names - currently keeps original model names unchanged."""
        self.normalized_models = {
            key: value for key, value in self.deployment_models.items()
        }


@dataclass
class ProxyConfig:
    """Main proxy configuration with multi-subaccount support."""

    subaccounts: Dict[str, SubAccountConfig] = field(default_factory=dict)
    secret_authentication_tokens: List[str] = field(default_factory=list)
    port: int = 3001
    host: str = "127.0.0.1"
    # Global model to subaccount mapping for load balancing
    model_to_subaccounts: Dict[str, List[str]] = field(default_factory=dict)

    def initialize(self):
        """Initialize all subaccounts and build model mappings."""
        for subaccount in self.subaccounts.values():
            subaccount.load_service_key()
            subaccount.normalize_model_names()

        # Build model to subaccounts mapping for load balancing
        self.build_model_mapping()

    def build_model_mapping(self):
        """Build a mapping of models to the subaccounts that have them."""
        self.model_to_subaccounts = {}
        for subaccount_name, subaccount in self.subaccounts.items():
            for model in subaccount.normalized_models.keys():
                if model not in self.model_to_subaccounts:
                    self.model_to_subaccounts[model] = []
                self.model_to_subaccounts[model].append(subaccount_name)
