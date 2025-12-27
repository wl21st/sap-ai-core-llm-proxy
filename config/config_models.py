"""
Configuration dataclasses for SAP AI Core LLM Proxy.

This module defines the core configuration structures used throughout the proxy.
"""

import json
import threading
from dataclasses import dataclass, field
from logging import Logger

from utils.logging_utils import get_server_logger
from utils.sdk_utils import extract_deployment_id

logger: Logger = get_server_logger(__name__)


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

    token: str | None = None
    expiry: float = 0
    lock: threading.Lock = field(default_factory=threading.Lock)


@dataclass
class SubAccountConfig:
    """Configuration for a single SAP AI Core subaccount."""

    name: str
    resource_group: str
    service_key_json: str
    model_to_deployment_urls: dict[str, list[str]]
    service_key: ServiceKey | None = None
    token_info: TokenInfo = field(default_factory=TokenInfo)
    model_to_deployment_ids: dict[str, list[str]] = field(default_factory=dict)

    def parse(self):
        """Parse and initialize subaccount configuration."""
        self.load_service_key()
        self.build_mapping()
        self.dump()

    def dump(self) -> None:
        """Dump subaccount configuration for debugging."""
        logger.info(
            "Parsed subaccount '%s' with deployment_urls: %s",
            self.name,
            self.model_to_deployment_urls,
        )

        logger.info(
            "Parsed subaccount '%s' with deployment_ids: %s",
            self.name,
            self.model_to_deployment_ids,
        )

    def load_service_key(self):
        """Load service key from file.

        This method imports load_config to avoid circular dependencies.
        """
        # NOTE: Replace with pydantic code
        with open(self.service_key_json, "r") as service_key_file:
            service_key_json = json.load(service_key_file)

        self.service_key: ServiceKey = ServiceKey(
            client_id=service_key_json.get("clientid"),
            client_secret=service_key_json.get("clientsecret"),
            auth_url=service_key_json.get("url"),
            identity_zone_id=service_key_json.get("identityzoneid"),
            api_url=service_key_json.get("serviceurls", {}).get("AI_API_URL"),
        )

    def build_mapping(self):
        """Normalize model names to url mapping"""
        for key, value in self.model_to_deployment_urls.items():
            model_name = key.strip()
            self.model_to_deployment_ids[model_name] = []
            for url in value:
                deployment_url = url.strip()
                deployment_id = extract_deployment_id(deployment_url)
                if deployment_id:
                    self.model_to_deployment_ids[model_name].append(deployment_id)


@dataclass
class ProxyConfig:
    """Main proxy configuration with multi-subaccount support."""

    subaccounts: dict[str, SubAccountConfig] = field(default_factory=dict)
    secret_authentication_tokens: list[str] = field(default_factory=list)
    port: int = 3001
    host: str = "127.0.0.1"
    # Global model to subaccount mapping for load balancing
    model_to_subaccounts: dict[str, list[str]] = field(default_factory=dict)

    def parse(self):
        """Build a mapping of models to the subaccounts that have them."""
        for subaccount in self.subaccounts.values():
            subaccount.parse()

        self.model_to_subaccounts = {}
        for subaccount_name, subaccount in self.subaccounts.items():
            for model in subaccount.model_to_deployment_urls.keys():
                if model not in self.model_to_subaccounts:
                    self.model_to_subaccounts[model] = []
                self.model_to_subaccounts[model].append(subaccount_name)

        """Dump proxy configuration in the log."""
        logger.info(
            "Proxy configured with subaccounts: %s", list(self.subaccounts.keys())
        )
        logger.info("Model to subaccounts mapping: %s", self.model_to_subaccounts)

    def get_subaccount(self, subaccount_name: str) -> SubAccountConfig:
        return self.subaccounts[subaccount_name]
