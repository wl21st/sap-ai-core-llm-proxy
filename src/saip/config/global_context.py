"""
Global application context for SAP AI Core LLM Proxy.

This module provides a singleton ProxyGlobalContext that holds the application
configuration and global services like token managers and SDK pools.
Similar to Spring Boot's ApplicationContext.
"""

import os
import threading
from logging import Logger

from saip.config.config_models import ProxyConfig
from saip.utils import logging_utils

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
        from saip.auth.token_manager import (
            TokenManager,
        )  # Import here to avoid circular import
        from saip.utils.sdk_pool import resolve_ca_cert_bundle

        self.config = config

        # Resolve CA certificate bundle for HTTPS connections
        logger.info("Resolving TLS CA certificate bundle...")
        self.ca_cert_bundle = resolve_ca_cert_bundle(config.ca_cert_bundle)
        if self.ca_cert_bundle:
            logger.info(f"CA certificate bundle resolved: {self.ca_cert_bundle}")
            # Configure boto3/botocore to use the resolved certificate bundle
            os.environ["AWS_CA_BUNDLE"] = self.ca_cert_bundle
            logger.info(f"Set AWS_CA_BUNDLE environment variable to: {self.ca_cert_bundle}")

        # Initialize token managers per subaccount with resolved certificate bundle
        self.token_managers = {}
        for sub_name, sub_config in config.subaccounts.items():
            self.token_managers[sub_name] = TokenManager(
                sub_config, self.ca_cert_bundle
            )
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
            from saip.auth.token_manager import TokenManager

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
