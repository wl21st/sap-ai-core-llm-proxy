"""
Configuration loading utilities for SAP AI Core LLM Proxy.

This module handles loading and parsing configuration from JSON files.
"""

import json
import re
import warnings
from logging import Logger

from typing import Optional
from pydantic import BaseModel, Field

from config.config_models import ProxyConfig, SubAccountConfig, ServiceKey, ModelFilters
from utils.logging_utils import get_server_logger
from utils.sdk_utils import fetch_all_deployments
from utils.exceptions import (
    ConfigValidationError,
    DeploymentFetchError,
)

logger: Logger = get_server_logger(__name__)


# ============================================================================
# PYDANTIC SCHEMAS FOR JSON VALIDATION
# ============================================================================
#
# NOTE: These Pydantic models intentionally duplicate the dataclasses in
# config_models.py. This separation serves different purposes:
#
# 1. **Pydantic Schemas (here)**: Used for JSON validation during config loading.
#    - Validates raw JSON structure and types from config.json
#    - Uses camelCase field names matching the JSON format (e.g., "subAccounts")
#    - Provides clear validation error messages for user-facing config errors
#
# 2. **Dataclasses (config_models.py)**: Used for runtime configuration state.
#    - Pythonic snake_case naming (e.g., "model_to_deployment_urls")
#    - Includes runtime-only fields not in JSON (e.g., "service_key", "token_info")
#    - Thread-safe token management and mutable state
#
# This two-layer approach ensures:
# - Clean JSON validation at the boundary (Pydantic)
# - Clean Python objects for internal use (dataclasses)
# - Separation of concerns between serialization and runtime state
#
# ============================================================================


class ModelFiltersSchema(BaseModel):
    """Pydantic model for model filters validation."""

    include_filters: Optional[list[str]] = Field(default=None)
    exclude_filters: Optional[list[str]] = Field(default=None)


class SubAccountConfigSchema(BaseModel):
    """Pydantic model for subaccount configuration validation."""

    resource_group: str = "default"
    service_key_json: str = ""
    # New Orchestration V2 field
    orchestration_url: Optional[str] = Field(default=None)
    # Deprecated: replaced by orchestration_url
    deployment_models: dict[str, list[str]] = Field(default_factory=dict)
    deployment_ids: dict[str, list[str]] = Field(default_factory=dict)


class ProxyConfigSchema(BaseModel):
    """Pydantic model for global proxy configuration validation."""

    secret_authentication_tokens: list[str] = Field(default_factory=list)
    port: int = 3001
    host: str = "127.0.0.1"
    model_filters: Optional[ModelFiltersSchema] = Field(default=None)
    subAccounts: dict[str, SubAccountConfigSchema] = Field(default_factory=dict)
    ca_cert_bundle: Optional[str] = Field(default=None)


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
) -> tuple[dict[str, list[str]], dict[str, str]]:
    """Apply model filters to a dictionary of models.

    Filter precedence logic:
    1. If include_filters exist, keep only models matching at least one pattern
    2. Then, if exclude_filters exist, remove models matching any pattern

    Args:
        models: Dictionary mapping model names to deployment URLs
        filters: ModelFilters object with include_filters/exclude_filters patterns

    Returns:
        Tuple of (filtered_models_dict, filtered_info_dict)
        - filtered_models_dict: Models that passed filtering
        - filtered_info_dict: Map of model_name -> filter_reason
    """
    if not filters or (not filters.include_filters and not filters.exclude_filters):
        return models, {}

    # Compile regex patterns
    include_patterns: list[re.Pattern[str]] = []
    exclude_patterns: list[re.Pattern[str]] = []

    if filters.include_filters:
        include_patterns = validate_regex_patterns(
            filters.include_filters, "include_filters"
        )

    if filters.exclude_filters:
        exclude_patterns = validate_regex_patterns(
            filters.exclude_filters, "exclude_filters"
        )

    filtered_models: dict[str, list[str]] = {}
    filtered_info: dict[str, str] = {}

    for model_name, urls in models.items():
        keep_model = True
        filter_reason = ""

        # Step 1: Apply include_filters first (if present)
        # If include patterns exist, only keep models that match at least one pattern
        if include_patterns:
            matches_include = any(
                pattern.search(model_name) for pattern in include_patterns
            )
            if not matches_include:
                keep_model = False
                filter_reason = f"did not match include_filters"

        # Step 2: Apply exclude_filters (if model passed include or no include filters)
        # Remove any models that match exclude patterns
        if keep_model and exclude_patterns:
            for pattern in exclude_patterns:
                if pattern.search(model_name):
                    keep_model = False
                    filter_reason = (
                        f"matched exclude_filters pattern: {pattern.pattern}"
                    )
                    break

        if keep_model:
            filtered_models[model_name] = urls
        else:
            filtered_info[model_name] = filter_reason

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
            include_filters=config_schema.model_filters.include_filters,
            exclude_filters=config_schema.model_filters.exclude_filters,
        )
        # Log filter configuration
        include_count = (
            len(model_filters.include_filters) if model_filters.include_filters else 0
        )
        exclude_count = (
            len(model_filters.exclude_filters) if model_filters.exclude_filters else 0
        )
        logger.info(
            f"Model filters configured: {include_count} include_filters, {exclude_count} exclude_filters"
        )
        if model_filters.include_filters:
            logger.info(f"  Include patterns: {model_filters.include_filters}")
        if model_filters.exclude_filters:
            logger.info(f"  Exclude patterns: {model_filters.exclude_filters}")

    # Create a proper ProxyConfig instance
    proxy_config = ProxyConfig(
        secret_authentication_tokens=config_schema.secret_authentication_tokens,
        port=config_schema.port,
        host=config_schema.host,
        model_filters=model_filters,
        ca_cert_bundle=config_schema.ca_cert_bundle,
    )

    # Parse each subAccount
    for sub_name, sub_config_schema in config_schema.subAccounts.items():
        # Emit deprecation warnings for old fields
        deprecated_fields_found: list[str] = []
        if sub_config_schema.deployment_models:
            deprecated_fields_found.append("deployment_models")
        if sub_config_schema.deployment_ids:
            deprecated_fields_found.append("deployment_ids")
        if deprecated_fields_found:
            msg = (
                f"Subaccount '{sub_name}': deprecated config fields detected: "
                f"{deprecated_fields_found}. "
                f"Please migrate to 'orchestration_url'. "
                f"These fields will be removed in a future version."
            )
            warnings.warn(msg, DeprecationWarning, stacklevel=2)
            logger.warning(msg)

        deployment_models = sub_config_schema.deployment_models
        models_before_filter = len(deployment_models)

        # Apply model filters if configured
        filtered_model_info: dict[str, str] = {}
        if model_filters:
            deployment_models, filtered_model_info = apply_model_filters(
                deployment_models, model_filters
            )

            # Log filtering results
            models_after_filter = len(deployment_models)

            logger.info(
                f"Subaccount '{sub_name}': {models_before_filter} models available, "
                f"{models_after_filter} models after filtering"
            )

            if filtered_model_info:
                logger.info(
                    f"Subaccount '{sub_name}': Filtered out {len(filtered_model_info)} models:"
                )
                for model_name, reason in filtered_model_info.items():
                    logger.info(f"  - {model_name}: {reason}")

            # Warn if all models filtered out
            if models_after_filter == 0:
                logger.warning(
                    f"Subaccount '{sub_name}': All models filtered out (zero models remaining)"
                )

        sub_account_config: SubAccountConfig = SubAccountConfig(
            name=sub_name,
            resource_group=sub_config_schema.resource_group,
            service_key_json=sub_config_schema.service_key_json,
            orchestration_url=sub_config_schema.orchestration_url,
            model_to_deployment_urls=deployment_models,
            model_to_deployment_ids=sub_config_schema.deployment_ids,
        )
        proxy_config.subaccounts[sub_name] = sub_account_config

    # Parse subaccounts: load service keys and build mappings
    for sub_name, sub_account_config in proxy_config.subaccounts.items():
        _load_service_key_for_subaccount(sub_account_config)
        if sub_account_config.orchestration_url:
            # Orchestration V2 path: explicit URL provided
            logger.info(
                f"Subaccount '{sub_name}': using Orchestration V2 URL: {sub_account_config.orchestration_url}"
            )
        else:
            # Try auto-discovery of orchestration URL
            discovered_url = _auto_discover_orchestration_url(sub_account_config)
            if discovered_url:
                sub_account_config.orchestration_url = discovered_url
                logger.info(
                    f"Subaccount '{sub_name}': auto-discovered orchestration URL: {discovered_url}"
                )
        _dump_subaccount_config(sub_account_config)

    # Build model to subaccounts mapping
    # For Orchestration V2 subaccounts: use a sentinel key "*" to indicate "any model"
    # For legacy subaccounts: build per-model mappings from model_to_deployment_urls
    proxy_config.model_to_subaccounts = {}
    for subaccount_name, subaccount in proxy_config.subaccounts.items():
        if subaccount.orchestration_url:
            # Orchestration V2: register subaccount under wildcard key
            if "*" not in proxy_config.model_to_subaccounts:
                proxy_config.model_to_subaccounts["*"] = []
            proxy_config.model_to_subaccounts["*"].append(subaccount_name)
        else:
            # Legacy: register per-model
            for model in subaccount.model_to_deployment_urls.keys():
                if model not in proxy_config.model_to_subaccounts:
                    proxy_config.model_to_subaccounts[model] = []
                proxy_config.model_to_subaccounts[model].append(subaccount_name)

    # Validate: each subaccount must have either orchestration_url or at least one deployment URL
    for sub_name, subaccount in proxy_config.subaccounts.items():
        if not subaccount.orchestration_url and not subaccount.model_to_deployment_urls:
            raise ConfigValidationError(
                f"Subaccount '{sub_name}' has no orchestration_url and no deployment_models configured. "
                f"Please add 'orchestration_url' to enable Orchestration V2 inference."
            )

    # Log configuration
    logger.info(
        "Proxy configured with subaccounts: %s", list(proxy_config.subaccounts.keys())
    )
    logger.info("Model to subaccounts mapping: %s", proxy_config.model_to_subaccounts)

    return proxy_config


def check_orchestration_url_health(
    orchestration_url: str, ca_cert_bundle: Optional[str] = None
) -> bool:
    """Check that the orchestration URL is reachable.

    Performs a lightweight HTTP HEAD/GET check to verify connectivity.
    This is a startup health check — failures are logged but do not crash the proxy.

    Args:
        orchestration_url: The orchestration deployment URL to check
        ca_cert_bundle: Optional CA cert bundle path for TLS verification

    Returns:
        True if the URL is reachable (HTTP 2xx/3xx/4xx), False on connection failure
    """
    import requests

    # Remove trailing /completion path for a lighter check
    base_url = orchestration_url.rstrip("/")
    if base_url.endswith("/completion"):
        base_url = base_url[: -len("/completion")]

    try:
        response = requests.head(
            base_url,
            timeout=5,
            verify=ca_cert_bundle if ca_cert_bundle else True,
            allow_redirects=True,
        )
        # Any HTTP response (even 401/403/404) means connectivity works
        logger.info(
            f"Orchestration URL health check passed: {base_url} → HTTP {response.status_code}"
        )
        return True
    except requests.exceptions.ConnectionError as e:
        logger.warning(
            f"Orchestration URL health check failed (connection error): {base_url} — {e}"
        )
        return False
    except requests.exceptions.Timeout:
        logger.warning(f"Orchestration URL health check timed out: {base_url}")
        return False
    except Exception as e:
        logger.warning(f"Orchestration URL health check error: {base_url} — {e}")
        return False


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


def _auto_discover_orchestration_url(
    sub_account_config: SubAccountConfig,
) -> Optional[str]:
    """Discover the orchestration service deployment URL from SAP AI Core.

    Calls GET /v2/lm/deployments and filters for deployments running the
    orchestration service (model_name contains 'orchestration' or
    configurationName contains 'orchestration').

    Args:
        sub_account_config: The subaccount config with a loaded service key

    Returns:
        Orchestration URL string if found, None otherwise
    """
    try:
        discovered_deployments = fetch_all_deployments(
            service_key=sub_account_config.service_key,
            resource_group=sub_account_config.resource_group,
        )
    except Exception as e:
        logger.warning(
            f"Could not fetch deployments for orchestration URL discovery in "
            f"'{sub_account_config.name}': {e}"
        )
        return None

    for dep in discovered_deployments:
        url = dep.get("url", "")
        model_name = dep.get("model_name") or ""
        # Orchestration service deployments typically have 'orchestration' in the path
        # or in their model/config name
        if url and (
            "orchestration" in url.lower() or "orchestration" in model_name.lower()
        ):
            logger.info(
                f"Auto-discovered orchestration URL for '{sub_account_config.name}': {url}"
            )
            return url

    logger.warning(
        f"No orchestration service deployment found in '{sub_account_config.name}'. "
        f"Please configure 'orchestration_url' explicitly."
    )
    return None


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
