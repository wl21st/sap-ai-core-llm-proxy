"""
Global application context for SAP AI Core LLM Proxy.

This module provides a singleton ProxyGlobalContext that holds the application
configuration and global services like token managers and SDK pools.
Similar to Spring Boot's ApplicationContext.
"""

import threading
from logging import Logger

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

        self.config = config
        # Initialize token managers per subaccount
        self.token_managers = {}
        for sub_name, sub_config in config.subaccounts.items():
            self.token_managers[sub_name] = TokenManager(sub_config)
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
            # Lazy create token manager
            from auth.token_manager import TokenManager

            self.token_managers[subaccount_name] = TokenManager(
                self.config.subaccounts[subaccount_name]
            )
        return self.token_managers[subaccount_name]

    def shutdown(self):
        """Shutdown the global context and cleanup resources."""
        # Cleanup token managers if needed
        self.token_managers.clear()
        logger.info("ProxyGlobalContext shutdown complete")
