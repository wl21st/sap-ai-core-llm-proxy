"""
Configuration loading utilities for SAP AI Core LLM Proxy.

This module handles loading and parsing configuration from JSON files.
"""

import json
from logging import Logger

from config import ProxyConfig, SubAccountConfig, ServiceKey
from utils.logging_utils import get_server_logger
from utils.sdk_utils import extract_deployment_id

logger: Logger = get_server_logger(__name__)


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

    # Parse subaccounts: load service keys and build mappings
    for sub_name, sub_account_config in proxy_config.subaccounts.items():
        _load_service_key_for_subaccount(sub_account_config)
        _build_mapping_for_subaccount(sub_account_config)
        _dump_subaccount_config(sub_account_config)

    # Build model to subaccounts mapping
    proxy_config.model_to_subaccounts = {}
    for subaccount_name, subaccount in proxy_config.subaccounts.items():
        for model in subaccount.model_to_deployment_urls.keys():
            if model not in proxy_config.model_to_subaccounts:
                proxy_config.model_to_subaccounts[model] = []
            proxy_config.model_to_subaccounts[model].append(subaccount_name)

    # Log configuration
    logger.info(
        "Proxy configured with subaccounts: %s", list(proxy_config.subaccounts.keys())
    )
    logger.info("Model to subaccounts mapping: %s", proxy_config.model_to_subaccounts)

    return proxy_config


def _load_service_key_for_subaccount(sub_account_config: SubAccountConfig):
    """Load service key from file for a subaccount.

    Args:
        sub_account_config: The subaccount config to update
    """
    with open(sub_account_config.service_key_json, "r") as service_key_file:
        service_key_json = json.load(service_key_file)

    sub_account_config.service_key = ServiceKey(
        client_id=service_key_json.get("clientid"),
        client_secret=service_key_json.get("clientsecret"),
        auth_url=service_key_json.get("url"),
        identity_zone_id=service_key_json.get("identityzoneid"),
        api_url=service_key_json.get("serviceurls", {}).get("AI_API_URL"),
    )


def _build_mapping_for_subaccount(sub_account_config: SubAccountConfig):
    """Build deployment ID mapping for a subaccount.

    Args:
        sub_account_config: The subaccount config to update
    """
    for key, value in sub_account_config.model_to_deployment_urls.items():
        model_name = key.strip()
        sub_account_config.model_to_deployment_ids[model_name] = []
        for url in value:
            deployment_url = url.strip()
            deployment_id = extract_deployment_id(deployment_url)
            if deployment_id:
                sub_account_config.model_to_deployment_ids[model_name].append(
                    deployment_id
                )


def _dump_subaccount_config(sub_account_config: SubAccountConfig):
    """Dump subaccount configuration for debugging.

    Args:
        sub_account_config: The subaccount config to log
    """
    logger.info(
        "Parsed subaccount '%s' with deployment_urls: %s",
        sub_account_config.name,
        sub_account_config.model_to_deployment_urls,
    )

    logger.info(
        "Parsed subaccount '%s' with deployment_ids: %s",
        sub_account_config.name,
        sub_account_config.model_to_deployment_ids,
    )
