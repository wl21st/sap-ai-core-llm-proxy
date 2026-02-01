"""
Configuration loading utilities for SAP AI Core LLM Proxy.

This module handles loading and parsing configuration from JSON files.
"""

import json
import re
from logging import Logger

from typing import Optional
from pydantic import BaseModel, Field, ValidationError

from config.config_models import ProxyConfig, SubAccountConfig, ServiceKey, ModelFilters
from utils.logging_utils import get_server_logger
from utils.sdk_utils import (
    extract_deployment_id,
    fetch_deployment_url,
    fetch_all_deployments,
)
from utils.exceptions import (
    ConfigValidationError,
    DeploymentFetchError,
    DeploymentResolutionError,
)
from utils.error_ids import ErrorIDs
from proxy_helpers import MODEL_ALIASES, Detector

logger: Logger = get_server_logger(__name__)


class ModelFiltersSchema(BaseModel):
    """Pydantic model for model filters validation."""

    include: Optional[list[str]] = Field(default=None)
    exclude: Optional[list[str]] = Field(default=None)


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
    model_filters: Optional[ModelFiltersSchema] = Field(default=None)
    subAccounts: dict[str, SubAccountConfigSchema] = Field(default_factory=dict)


def validate_regex_patterns(
    patterns: list[str], filter_type: str
) -> list[re.Pattern[str]]:
    """Validate and compile regex patterns.

    Args:
        patterns: List of regex pattern strings to validate
        filter_type: Type of filter ('include' or 'exclude') for error messages

    Returns:
        List of compiled regex Pattern objects

    Raises:
        ConfigValidationError: If any pattern is invalid
    """
    compiled_patterns: list[re.Pattern[str]] = []

    for pattern in patterns:
        try:
            compiled_pattern = re.compile(pattern)
            compiled_patterns.append(compiled_pattern)
        except re.error as e:
            raise ConfigValidationError(
                f"Invalid regex pattern in {filter_type} filters: '{pattern}' - {str(e)}"
            )

    return compiled_patterns


def apply_model_filters(
    models: dict[str, list[str]], filters: ModelFilters
) -> tuple[dict[str, list[str]], list[tuple[str, str, str]]]:
    """Apply model filters to a dictionary of models.

    Filter precedence logic (per spec):
    1. If include patterns exist, keep only models matching at least one include pattern
    2. Then, if exclude patterns exist, remove models matching any exclude pattern

    Args:
        models: Dictionary mapping model names to deployment URLs
        filters: ModelFilters object with include/exclude patterns

    Returns:
        Tuple of (filtered_models_dict, filtered_info_list)
        - filtered_models_dict: Models that passed filtering
        - filtered_info_list: List of (model_name, filter_type, pattern) for filtered models
    """
    if not filters or (not filters.include and not filters.exclude):
        return models, []

    # Compile regex patterns
    include_patterns: list[re.Pattern[str]] = []
    exclude_patterns: list[re.Pattern[str]] = []

    if filters.include:
        include_patterns = validate_regex_patterns(filters.include, "include")

    if filters.exclude:
        exclude_patterns = validate_regex_patterns(filters.exclude, "exclude")

    filtered_models: dict[str, list[str]] = {}
    filtered_info: list[tuple[str, str, str]] = []

    for model_name, urls in models.items():
        keep_model = True
        filter_reason = ("", "")  # (filter_type, pattern)

        # Filter precedence per spec: include first, then exclude
        # This allows exclude filters to act as exceptions to the include list
        # Example: include ["^gpt-.*"], exclude [".*-preview$"] -> keeps gpt-4 but not gpt-4-preview

        # Step 1: Apply include filters first (if present)
        # If include patterns exist, only keep models that match at least one pattern
        if include_patterns:
            matches_include = any(
                pattern.match(model_name) for pattern in include_patterns
            )
            if not matches_include:
                keep_model = False
                # Find which pattern would have matched for logging
                for pattern in include_patterns:
                    filter_reason = ("include", pattern.pattern)
                    break
                if not filter_reason[1]:  # If no specific pattern, use generic message
                    filter_reason = ("include", "no matching include pattern")

        # Step 2: Apply exclude filters (if model passed include or no include filters)
        # Remove any models that match exclude patterns
        if keep_model and exclude_patterns:
            for pattern in exclude_patterns:
                if pattern.match(model_name):
                    keep_model = False
                    filter_reason = ("exclude", pattern.pattern)
                    break

        if keep_model:
            filtered_models[model_name] = urls
        else:
            filtered_info.append((model_name, filter_reason[0], filter_reason[1]))

    return filtered_models, filtered_info


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

    # Parse model filters if present
    model_filters: Optional[ModelFilters] = None
    if config_schema.model_filters:
        model_filters = ModelFilters(
            include=config_schema.model_filters.include,
            exclude=config_schema.model_filters.exclude,
        )
        # Log filter configuration
        include_count = len(model_filters.include) if model_filters.include else 0
        exclude_count = len(model_filters.exclude) if model_filters.exclude else 0
        logger.info(
            f"Model filters configured: include={include_count} patterns, exclude={exclude_count} patterns"
        )

    # Create a proper ProxyConfig instance
    proxy_config = ProxyConfig(
        secret_authentication_tokens=config_schema.secret_authentication_tokens,
        port=config_schema.port,
        host=config_schema.host,
        model_filters=model_filters,
    )

    # Parse each subAccount
    for sub_name, sub_config_schema in config_schema.subAccounts.items():
        deployment_models = sub_config_schema.deployment_models
        models_before_filter = len(deployment_models)

        # Apply model filters if configured
        filtered_model_info: list[tuple[str, str, str]] = []
        if model_filters:
            deployment_models, filtered_model_info = apply_model_filters(
                deployment_models, model_filters
            )

            # Log filtering results
            models_after_filter = len(deployment_models)
            filtered_model_names = [info[0] for info in filtered_model_info]

            logger.info(
                f"Subaccount '{sub_name}': {models_before_filter} models configured, "
                f"{models_after_filter} after filtering"
            )

            if filtered_model_names:
                logger.info(
                    f"Subaccount '{sub_name}': Filtered models: {', '.join(filtered_model_names)}"
                )

                # DEBUG-level logging with pattern details
                for model_name, filter_type, pattern in filtered_model_info:
                    logger.debug(
                        f"Filtered model '{model_name}' by {filter_type} filter: {pattern}"
                    )

            # Warn if all models filtered out
            if models_after_filter == 0:
                logger.warning(
                    f"Subaccount '{sub_name}': All models filtered out (zero models remaining)"
                )

        sub_account_config: SubAccountConfig = SubAccountConfig(
            name=sub_name,
            resource_group=sub_config_schema.resource_group,
            service_key_json=sub_config_schema.service_key_json,
            model_to_deployment_urls=deployment_models,
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

    # Check if service_key is initialized and has required fields for auto-discovery
    has_valid_service_key = (
        hasattr(sub_account_config, "service_key")
        and sub_account_config.service_key is not None
        and hasattr(sub_account_config.service_key, "api_url")
        and sub_account_config.service_key.api_url is not None
        and hasattr(sub_account_config.service_key, "auth_url")
        and sub_account_config.service_key.auth_url is not None
    )

    if has_valid_service_key:
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
                        not in sub_account_config.model_to_deployment_urls[
                            backend_model
                        ]
                    ):
                        sub_account_config.model_to_deployment_urls[
                            backend_model
                        ].append(url)
                        logger.debug(f"Auto-discovered: {backend_model} -> {url}")

                    # Register aliases
                    if backend_model in MODEL_ALIASES:
                        for alias in MODEL_ALIASES[backend_model]:
                            if alias not in sub_account_config.model_to_deployment_urls:
                                sub_account_config.model_to_deployment_urls[alias] = []

                            if (
                                url
                                not in sub_account_config.model_to_deployment_urls[
                                    alias
                                ]
                            ):
                                sub_account_config.model_to_deployment_urls[
                                    alias
                                ].append(url)
                                logger.debug(f"Auto-aliased: {alias} -> {url}")

        except DeploymentFetchError as e:
            logger.error(
                f"Auto-discovery failed for subaccount '{sub_account_config.name}': {e}. "
                f"Check service key credentials and network connectivity.",
                extra={
                    "error_id": ErrorIDs.AUTODISCOVERY_AUTH_FAILED,
                    "subaccount": sub_account_config.name,
                },
            )
            raise ConfigValidationError(
                f"Auto-discovery failed for '{sub_account_config.name}': {e}"
            ) from e
        except Exception as e:
            logger.error(
                f"Unexpected error during auto-discovery for '{sub_account_config.name}': {e}",
                extra={
                    "error_id": ErrorIDs.AUTODISCOVERY_UNEXPECTED_ERROR,
                    "subaccount": sub_account_config.name,
                },
            )
            raise ConfigValidationError(
                f"Auto-discovery failed: {e}. Check service key and network connectivity."
            ) from e
    else:
        logger.debug(
            f"Skipping auto-discovery for subaccount '{sub_account_config.name}': "
            f"service key not initialized or missing required fields (api_url, auth_url)"
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
            except ValueError as e:
                logger.error(
                    f"Invalid deployment ID '{deployment_id}' for model '{model_name}': {e}",
                    extra={"error_id": ErrorIDs.INVALID_DEPLOYMENT_ID},
                )
                raise ConfigValidationError(
                    f"Invalid deployment ID '{deployment_id}' for model '{model_name}'. "
                    f"Check your config.json and verify deployment exists in SAP AI Core console."
                ) from e
            except Exception as e:
                # Check if it's a 404 error by examining the exception
                error_msg = str(e).lower()
                if "404" in error_msg or "not found" in error_msg:
                    logger.error(
                        f"Deployment '{deployment_id}' not found for model '{model_name}'",
                        extra={"error_id": ErrorIDs.DEPLOYMENT_NOT_FOUND},
                    )
                    raise ConfigValidationError(
                        f"Deployment '{deployment_id}' not found. Verify it exists in SAP AI Core."
                    ) from e

                logger.error(
                    f"Failed to resolve deployment '{deployment_id}': {e}",
                    extra={"error_id": ErrorIDs.DEPLOYMENT_RESOLUTION_FAILED},
                )
                raise ConfigValidationError(
                    f"Could not resolve deployment '{deployment_id}' to URL. "
                    f"Check credentials and deployment status."
                ) from e

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
