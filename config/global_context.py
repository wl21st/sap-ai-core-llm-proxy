"""
Global application context for SAP AI Core LLM Proxy.

This module provides a singleton ProxyGlobalContext that holds the application
configuration and global services like token managers and SDK pools.
Similar to Spring Boot's ApplicationContext.
"""

import os
import threading
from logging import Logger
from typing import Optional

from config.config_models import ProxyConfig
from utils import logging_utils

logger: Logger = logging_utils.get_server_logger(__name__)


class ProxyGlobalContext:
    """Singleton global context holding configuration and services."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def initialize(self, config: ProxyConfig):
        """Initialize the global context with configuration.

        Args:
            config: The loaded ProxyConfig instance
        """
        from auth.token_manager import (
            TokenManager,
        )  # Import here to avoid circular import
        from utils.cert_utils import resolve_ca_cert_bundle

        self.config = config

        # Resolve CA certificate bundle for HTTPS connections
        logger.info("Resolving TLS CA certificate bundle...")
        self.ca_cert_bundle = resolve_ca_cert_bundle(config.ca_cert_bundle)
        if self.ca_cert_bundle:
            logger.info(f"CA certificate bundle resolved: {self.ca_cert_bundle}")
            # Configure boto3/botocore to use the resolved certificate bundle
            logger.info(
                "CA bundle set: %s", self.ca_cert_bundle
            )

        # Initialize token managers per subaccount with resolved certificate bundle
        self.token_managers = {}
        for sub_name, sub_config in config.subaccounts.items():
            self.token_managers[sub_name] = TokenManager(
                sub_config, self.ca_cert_bundle
            )

        # Startup health checks for Orchestration V2 URLs
        from config.config_parser import check_orchestration_url_health

        for sub_name, sub_config in config.subaccounts.items():
            if sub_config.orchestration_url:
                healthy = check_orchestration_url_health(
                    sub_config.orchestration_url, self.ca_cert_bundle
                )
                if not healthy:
                    logger.warning(
                        "Orchestration URL for subaccount '%s' is not reachable at startup: %s. "
                        "Requests to this subaccount may fail until connectivity is restored.",
                        sub_name,
                        sub_config.orchestration_url,
                    )

        # Populate the foundation model registry
        from utils.foundation_model_registry import get_registry

        registry = get_registry()
        registry.populate(
            subaccounts=config.subaccounts,
            token_managers=self.token_managers,
            ca_cert_bundle=self.ca_cert_bundle,
        )
        self.foundation_model_registry = registry

        # Load model aliases (config/aliases.json if present, else defaults)
        from utils.model_aliases import load_aliases_from_file, DEFAULT_ALIASES

        # Look for aliases.json in the config/ subdirectory of the CWD
        aliases_path = os.path.join("config", "aliases.json")
        self.model_aliases = load_aliases_from_file(aliases_path, base_aliases=DEFAULT_ALIASES)

        # Initialize OrchestrationClient singleton with resolved CA bundle
        from utils.orchestration_client import OrchestrationClient
        import utils.orchestration_client as _orch_module

        _orch_module._client = OrchestrationClient(ca_cert_bundle=self.ca_cert_bundle)
        self.orchestration_client = _orch_module._client

        logger.info(
            "ProxyGlobalContext initialized with %d subaccounts",
            len(config.subaccounts),
        )

    def get_token_manager(self, subaccount_name: str):
        """Get the token manager for a specific subaccount.

        Args:
            subaccount_name: Name of the subaccount

        Returns:
            TokenManager instance for the subaccount

        Raises:
            KeyError: If subaccount not found
        """
        if subaccount_name not in self.token_managers:
            if subaccount_name not in self.config.subaccounts:
                raise KeyError(f"Subaccount '{subaccount_name}' not found in config")
            # Lazy create token manager with resolved certificate bundle
            from auth.token_manager import TokenManager

            self.token_managers[subaccount_name] = TokenManager(
                self.config.subaccounts[subaccount_name], self.ca_cert_bundle
            )
        return self.token_managers[subaccount_name]

    def get_ca_cert_bundle(self) -> str | None:
        """Get the resolved CA certificate bundle path.

        Returns:
            Path to CA certificate bundle or None if using defaults
        """
        return self.ca_cert_bundle

    def shutdown(self):
        """Shutdown the global context and cleanup resources."""
        # Cleanup token managers if needed
        self.token_managers.clear()
        logger.info("ProxyGlobalContext shutdown complete")
