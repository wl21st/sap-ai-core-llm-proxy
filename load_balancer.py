"""
Load balancing and model resolution for SAP AI Core LLM Proxy.

This module handles model name resolution (including fallbacks) and
round-robin load balancing across subaccounts.
"""

from proxy_helpers import Detector
from utils.logging_utils import get_server_logger

logger = get_server_logger(__name__)

# Default model constants
DEFAULT_CLAUDE_MODEL = "anthropic--claude-4.5-sonnet"
DEFAULT_GEMINI_MODEL = "gemini-2.5-pro"
DEFAULT_GPT_MODEL = "gpt-4.1"

# Module-level counter storage for load balancing
_load_balance_counters: dict = {}


def resolve_model_name(model_name: str, proxy_config) -> str | None:
    """
    Resolve a model name to an available model in the configuration.

    Handles aliases like 'opus-4.5' -> 'anthropic--claude-4.5-opus'.
    Returns the resolved model name or None if no fallback is found.

    Args:
        model_name: The requested model name (may be an alias)
        proxy_config: The proxy configuration object

    Returns:
        The resolved model name that exists in configuration, or None
    """
    # Check if model already exists in config
    if model_name in proxy_config.model_to_subaccounts:
        return model_name

    model_lower = model_name.lower()

    # Try fallback models based on model type
    if Detector.is_claude_model(model_name):
        # Build fallback list based on variant in requested model
        fallback_models = []
        if "opus" in model_lower:
            fallback_models = [
                "anthropic--claude-4.5-opus",
                "anthropic--claude-4-opus",
            ]
        elif "haiku" in model_lower:
            fallback_models = [
                "anthropic--claude-4-haiku",
                "anthropic--claude-3.5-haiku",
            ]
        else:
            # Default to sonnet for unspecified or sonnet variants
            fallback_models = [
                "anthropic--claude-4.5-sonnet",
                "anthropic--claude-4-sonnet",
                "anthropic--claude-3.7-sonnet",
            ]

        for fallback in fallback_models:
            if fallback in proxy_config.model_to_subaccounts:
                logger.info(f"Resolved model '{model_name}' to '{fallback}'")
                return fallback
    elif Detector.is_gemini_model(model_name):
        fallback_models = [DEFAULT_GEMINI_MODEL]
        for fallback in fallback_models:
            if fallback in proxy_config.model_to_subaccounts:
                logger.info(f"Resolved model '{model_name}' to '{fallback}'")
                return fallback
    else:
        # For other models, try GPT fallback
        fallback_models = [DEFAULT_GPT_MODEL]
        for fallback in fallback_models:
            if fallback in proxy_config.model_to_subaccounts:
                logger.info(f"Resolved model '{model_name}' to '{fallback}'")
                return fallback

    return None


def load_balance_url(selected_model_name: str, proxy_config) -> tuple[str, str, str, str]:
    """
    Load balance requests for a model across all subAccounts that have it deployed.

    Args:
        selected_model_name: Name of the model to load balance
        proxy_config: The proxy configuration object

    Returns:
        Tuple of (selected_url, subaccount_name, resource_group, final_model_name)

    Raises:
        ValueError: If no subAccounts have the requested model
    """
    global _load_balance_counters

    # Get list of subAccounts that have this model
    if (
        selected_model_name not in proxy_config.model_to_subaccounts
        or not proxy_config.model_to_subaccounts[selected_model_name]
    ):
        # Check if it's a Claude or Gemini model and try fallback
        if Detector.is_claude_model(selected_model_name):
            logger.info(
                f"Claude model '{selected_model_name}' not found, trying fallback models"
            )
            # Build fallback list based on variant in requested model
            model_lower = selected_model_name.lower()
            if "opus" in model_lower:
                fallback_models = [
                    "anthropic--claude-4.5-opus",
                    "anthropic--claude-4-opus",
                ]
            elif "haiku" in model_lower:
                fallback_models = [
                    "anthropic--claude-4-haiku",
                    "anthropic--claude-3.5-haiku",
                ]
            else:
                # Default to sonnet for unspecified or sonnet variants
                fallback_models = [
                    "anthropic--claude-4.5-sonnet",
                    "anthropic--claude-4-sonnet",
                    "anthropic--claude-3.7-sonnet",
                ]
            for fallback in fallback_models:
                if (
                    fallback in proxy_config.model_to_subaccounts
                    and proxy_config.model_to_subaccounts[fallback]
                ):
                    logger.info(
                        f"Using fallback Claude model '{fallback}' for '{selected_model_name}'"
                    )
                    selected_model_name = fallback
                    break
            else:
                logger.error("No Claude models available in any subAccount")
                raise ValueError(
                    f"Claude model '{selected_model_name}' and fallbacks not available in any subAccount"
                )
        elif Detector.is_gemini_model(selected_model_name):
            logger.info(
                f"Gemini model '{selected_model_name}' not found, trying fallback models"
            )
            # Try common Gemini model fallbacks
            fallback_models = ["gemini-2.5-pro"]
            for fallback in fallback_models:
                if (
                    fallback in proxy_config.model_to_subaccounts
                    and proxy_config.model_to_subaccounts[fallback]
                ):
                    logger.info(
                        f"Using fallback Gemini model '{fallback}' for '{selected_model_name}'"
                    )
                    selected_model_name = fallback
                    break
            else:
                logger.error("No Gemini models available in any subAccount")
                raise ValueError(
                    f"Gemini model '{selected_model_name}' and fallbacks not available in any subAccount"
                )
        else:
            # For other models, try common fallbacks
            logger.warning(
                f"Model '{selected_model_name}' not found, trying fallback models"
            )
            fallback_models = [DEFAULT_GPT_MODEL]
            for fallback in fallback_models:
                if (
                    fallback in proxy_config.model_to_subaccounts
                    and proxy_config.model_to_subaccounts[fallback]
                ):
                    logger.info(
                        f"Using fallback model '{fallback}' for '{selected_model_name}'"
                    )
                    selected_model_name = fallback
                    break
            else:
                logger.error(
                    f"No subAccounts with model '{selected_model_name}' or fallbacks found"
                )
                raise ValueError(
                    f"Model '{selected_model_name}' and fallbacks not available in any subAccount"
                )

    subaccount_names = proxy_config.model_to_subaccounts[selected_model_name]

    # Create counter for this model if it doesn't exist
    if selected_model_name not in _load_balance_counters:
        _load_balance_counters[selected_model_name] = 0

    # Select subAccount using round-robin
    subaccount_index = _load_balance_counters[selected_model_name] % len(
        subaccount_names
    )
    selected_subaccount: str = subaccount_names[subaccount_index]

    # Increment counter for next request
    _load_balance_counters[selected_model_name] += 1

    # Get the model URL list from the selected subAccount
    subaccount = proxy_config.subaccounts[selected_subaccount]
    url_list = subaccount.model_to_deployment_urls.get(selected_model_name, [])

    if not url_list:
        logger.error(
            f"Model '{selected_model_name}' listed for subAccount '{selected_subaccount}' but no URLs found"
        )
        raise ValueError(
            f"Configuration error: No URLs for model '{selected_model_name}' in subAccount '{selected_subaccount}'"
        )

    # Select URL using round-robin within the subAccount
    url_counter_key = f"{selected_subaccount}:{selected_model_name}"
    if url_counter_key not in _load_balance_counters:
        _load_balance_counters[url_counter_key] = 0

    url_index = _load_balance_counters[url_counter_key] % len(url_list)
    selected_url: str = url_list[url_index]

    # Increment URL counter for next request
    _load_balance_counters[url_counter_key] += 1

    # Get resource group for the selected subAccount
    selected_resource_group: str = subaccount.resource_group

    logger.info(
        f"Selected subAccount '{selected_subaccount}' and URL '{selected_url}' for model '{selected_model_name}'"
    )
    return (
        selected_url,
        selected_subaccount,
        selected_resource_group,
        selected_model_name,
    )


def reset_counters():
    """Reset all load balancing counters. Useful for testing."""
    global _load_balance_counters
    _load_balance_counters = {}


def get_counters() -> dict:
    """Get the current load balancing counters. Useful for testing and debugging."""
    return _load_balance_counters.copy()
