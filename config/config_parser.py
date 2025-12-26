"""
Configuration loading utilities for SAP AI Core LLM Proxy.

This module handles loading and parsing configuration from JSON files.
"""

import json

from config import ProxyConfig, SubAccountConfig


def load_proxy_config(file_path: str) -> ProxyConfig:
    """Load configuration from a JSON file with support for multiple subAccounts.

    Args:
        file_path: Path to the JSON configuration file

    Returns:
        ProxyConfig instance if new format with subAccounts, otherwise raw JSON dict

    Raises:
        FileNotFoundError: If the configuration file doesn't exist
        json.JSONDecodeError: If the file contains invalid JSON
    """
    with open(file_path, "r") as file:
        config_json = json.load(file)

    # Create a proper ProxyConfig instance
    proxy_config = ProxyConfig(
        secret_authentication_tokens=config_json.get(
            "secret_authentication_tokens", []
        ),
        port=config_json.get("port", 3001),
        host=config_json.get("host", "127.0.0.1"),
    )

    # Parse each subAccount
    # NOTE: Remove hard-coded json element names and replace with pydantic models later
    for sub_name, sub_config in config_json.get("subAccounts", {}).items():
        sub_account_config: SubAccountConfig = SubAccountConfig(
            name=sub_name,
            resource_group=sub_config.get("resource_group", "default"),
            service_key_json=sub_config.get("service_key_json", ""),
            model_to_deployment_urls=sub_config.get("deployment_models", {}),
        )
        proxy_config.subaccounts[sub_name] = sub_account_config

    proxy_config.parse()

    return proxy_config
