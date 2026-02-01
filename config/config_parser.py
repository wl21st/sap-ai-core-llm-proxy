"""
Configuration loading utilities for SAP AI Core LLM Proxy.

This module handles loading and parsing configuration from JSON files.
"""

import json
from logging import Logger

from pydantic import BaseModel, Field

from config import ProxyConfig, SubAccountConfig, ServiceKey
from utils.logging_utils import get_server_logger
from utils.sdk_utils import (
    extract_deployment_id,
    fetch_deployment_url,
    fetch_all_deployments,
)
from proxy_helpers import MODEL_ALIASES, Detector

logger: Logger = get_server_logger(__name__)


class SubAccountConfigSchema(BaseModel):
    """Pydantic model for subaccount configuration validation."""

    resource_group: str = "default"
    service_key_json: str = ""
    deployment_models: dict[str, list[str]] = Field(default_factory=dict)
    deployment_ids: dict[str, list[str]] = Field(default_factory=dict)


class ProxyConfigSchema(BaseModel):
    """Pydantic model for global proxy configuration validation."""

    secret_authentication_tokens: list[str] = Field(default_factory=list)
    port: int = 3001
    host: str = "127.0.0.1"
    subAccounts: dict[str, SubAccountConfigSchema] = Field(default_factory=dict)


def load_proxy_config(file_path: str) -> ProxyConfig:
    """Load configuration from a JSON file with support for multiple subAccounts.

    Args:
        file_path: Path to the JSON configuration file

    Returns:
        ProxyConfig instance if new format with subAccounts, otherwise raw JSON dict

    Raises:
        FileNotFoundError: If the configuration file doesn't exist
        json.JSONDecodeError: If the file contains invalid JSON
        pydantic.ValidationError: If the configuration is invalid
    """
    with open(file_path, "r") as file:
        config_json = json.load(file)

    # Validate with Pydantic
    config_schema = ProxyConfigSchema.model_validate(config_json)

    # Create a proper ProxyConfig instance
    proxy_config = ProxyConfig(
        secret_authentication_tokens=config_schema.secret_authentication_tokens,
        port=config_schema.port,
        host=config_schema.host,
    )

    # Parse each subAccount
    for sub_name, sub_config_schema in config_schema.subAccounts.items():
        sub_account_config: SubAccountConfig = SubAccountConfig(
            name=sub_name,
            resource_group=sub_config_schema.resource_group,
            service_key_json=sub_config_schema.service_key_json,
            model_to_deployment_urls=sub_config_schema.deployment_models,
            model_to_deployment_ids=sub_config_schema.deployment_ids,
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

    This function handles both:
    1. Deployment IDs configured in model_to_deployment_ids (fetches URLs via SDK)
    2. Deployment URLs configured in model_to_deployment_urls (extracts IDs for backward compatibility)

    Args:
        sub_account_config: The subaccount config to update
    """
    # 0. Auto-discovery of deployments (New Feature)
    discovered_deployments = []
    try:
        logger.info(
            f"Starting auto-discovery for subaccount '{sub_account_config.name}'"
        )
        discovered_deployments = fetch_all_deployments(
            service_key=sub_account_config.service_key,
            resource_group=sub_account_config.resource_group,
        )

        for dep in discovered_deployments:
            url = dep.get("url")
            backend_model = dep.get("model_name")

            if url and backend_model:
                # Register under raw backend model name
                if backend_model not in sub_account_config.model_to_deployment_urls:
                    sub_account_config.model_to_deployment_urls[backend_model] = []

                if (
                    url
                    not in sub_account_config.model_to_deployment_urls[backend_model]
                ):
                    sub_account_config.model_to_deployment_urls[backend_model].append(
                        url
                    )
                    logger.debug(f"Auto-discovered: {backend_model} -> {url}")

                # Register aliases
                if backend_model in MODEL_ALIASES:
                    for alias in MODEL_ALIASES[backend_model]:
                        if alias not in sub_account_config.model_to_deployment_urls:
                            sub_account_config.model_to_deployment_urls[alias] = []

                        if (
                            url
                            not in sub_account_config.model_to_deployment_urls[alias]
                        ):
                            sub_account_config.model_to_deployment_urls[alias].append(
                                url
                            )
                            logger.debug(f"Auto-aliased: {alias} -> {url}")

    except Exception as e:
        logger.error(
            "Auto-discovery failed for subaccount '%s': %s",
            sub_account_config.name,
            e,
        )

    # Build lookup map for validation (ID -> Model Name)
    deployment_id_to_model = {
        d["id"]: d.get("model_name") for d in discovered_deployments if d.get("id")
    }

    # First, resolve deployment IDs to URLs using the SDK (new feature)
    for (
        model_name,
        deployment_ids,
    ) in sub_account_config.model_to_deployment_ids.items():
        model_name = model_name.strip()
        if model_name not in sub_account_config.model_to_deployment_urls:
            sub_account_config.model_to_deployment_urls[model_name] = []

        for deployment_id in deployment_ids:
            deployment_id = deployment_id.strip()

            # Validation: Check if deployment exists and matches model
            if deployment_id in deployment_id_to_model:
                backend_model = deployment_id_to_model[deployment_id]
                is_valid, reason = Detector.validate_model_mapping(
                    model_name, backend_model
                )
                if not is_valid:
                    logger.warning(
                        "Configuration mismatch: Model '%s' mapped to deployment '%s' which is running '%s' (%s)",
                        model_name,
                        deployment_id,
                        backend_model,
                        reason,
                    )
            elif discovered_deployments:
                # Only warn if discovery succeeded but ID wasn't found
                logger.warning(
                    "Configuration warning: Deployment '%s' mapped to model '%s' not found in subaccount",
                    deployment_id,
                    model_name,
                )

            try:
                deployment_url = fetch_deployment_url(
                    service_key=sub_account_config.service_key,
                    deployment_id=deployment_id,
                    resource_group=sub_account_config.resource_group,
                )
                if (
                    deployment_url
                    not in sub_account_config.model_to_deployment_urls[model_name]
                ):
                    sub_account_config.model_to_deployment_urls[model_name].append(
                        deployment_url
                    )
                    logger.info(
                        "Resolved deployment ID '%s' to URL for model '%s' in subaccount '%s'",
                        deployment_id,
                        model_name,
                        sub_account_config.name,
                    )
            except Exception as e:
                logger.error(
                    "Failed to resolve deployment ID '%s' for model '%s' in subaccount '%s': %s",
                    deployment_id,
                    model_name,
                    sub_account_config.name,
                    e,
                )
                # Continue with other deployments - don't crash the entire server

    # Then, extract deployment IDs from URLs for backward compatibility
    for model_name, urls in sub_account_config.model_to_deployment_urls.items():
        model_name = model_name.strip()
        if model_name not in sub_account_config.model_to_deployment_ids:
            sub_account_config.model_to_deployment_ids[model_name] = []

        for url in urls:
            deployment_url = url.strip()
            try:
                deployment_id = extract_deployment_id(deployment_url)

                # Validation: Check if deployment exists and matches model
                if deployment_id in deployment_id_to_model:
                    backend_model = deployment_id_to_model[deployment_id]
                    is_valid, reason = Detector.validate_model_mapping(
                        model_name, backend_model
                    )
                    if not is_valid:
                        logger.warning(
                            "Configuration mismatch: Model '%s' mapped to deployment '%s' which is running '%s' (%s)",
                            model_name,
                            deployment_id,
                            backend_model,
                            reason,
                        )
                elif discovered_deployments:
                    # Only warn if discovery succeeded but ID wasn't found
                    logger.warning(
                        "Configuration warning: Deployment '%s' mapped to model '%s' not found in subaccount",
                        deployment_id,
                        model_name,
                    )

                if (
                    deployment_id
                    and deployment_id
                    not in sub_account_config.model_to_deployment_ids[model_name]
                ):
                    sub_account_config.model_to_deployment_ids[model_name].append(
                        deployment_id
                    )
            except ValueError as e:
                logger.warning(
                    "Could not extract deployment ID from URL '%s' for model '%s': %s",
                    deployment_url,
                    model_name,
                    e,
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
