"""
Load balancing and model resolution for SAP AI Core LLM Proxy.

This module handles model name resolution (including fallbacks) and
round-robin load balancing across subaccounts.
"""

import threading

from utils.logging_utils import get_server_logger

logger = get_server_logger(__name__)

# Default model constants
DEFAULT_CLAUDE_MODEL = "anthropic--claude-4.5-sonnet"
DEFAULT_GEMINI_MODEL = "gemini-2.5-pro"
DEFAULT_GPT_MODEL = "gpt-4.1"

# Module-level counter storage for load balancing
_load_balance_counters: dict = {}
_counters_lock = threading.Lock()


def resolve_model_name(model_name: str, proxy_config) -> str | None:
    """
    Resolve a model name to an available model in the configuration.

    For Orchestration V2 subaccounts, all models route through the wildcard
    key "*" so any model name is considered "available" — validation against
    the foundation model registry happens separately in the chat router.

    For legacy per-deployment subaccounts, performs alias-based fallback.

    Args:
        model_name: The requested model name (may be an alias)
        proxy_config: The proxy configuration object

    Returns:
        The resolved model name that exists in configuration, or None
    """
    # Orchestration V2 path: if any subaccount uses the wildcard key, all
    # model names are routable (registry validation handled in chat router).
    if "*" in proxy_config.model_to_subaccounts:
        return model_name

    # Legacy path: check exact match first
    if model_name in proxy_config.model_to_subaccounts:
        return model_name

    model_lower = model_name.lower()

    # Determine model family for legacy fallback
    is_claude = any(
        token in model_lower
        for token in ("claude", "anthropic--", "sonnet", "haiku", "opus")
    )
    is_gemini = "gemini" in model_lower

    if is_claude:
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
            fallback_models = [
                "anthropic--claude-4.5-sonnet",
                "anthropic--claude-4-sonnet",
                "anthropic--claude-3.7-sonnet",
            ]
        for fallback in fallback_models:
            if fallback in proxy_config.model_to_subaccounts:
                logger.info("Resolved model '%s' to '%s'", model_name, fallback)
                return fallback
    elif is_gemini:
        fallback_models = [DEFAULT_GEMINI_MODEL]
        for fallback in fallback_models:
            if fallback in proxy_config.model_to_subaccounts:
                logger.info("Resolved model '%s' to '%s'", model_name, fallback)
                return fallback
    else:
        fallback_models = [DEFAULT_GPT_MODEL]
        for fallback in fallback_models:
            if fallback in proxy_config.model_to_subaccounts:
                logger.info("Resolved model '%s' to '%s'", model_name, fallback)
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
        model_lower_lb = selected_model_name.lower()
        _is_claude = any(
            t in model_lower_lb for t in ("claude", "anthropic--", "sonnet", "haiku", "opus")
        )
        _is_gemini = "gemini" in model_lower_lb
        if _is_claude:
            logger.info(
                f"Claude model '{selected_model_name}' not found, trying fallback models"
            )
            # Build fallback list based on variant in requested model
            if "opus" in model_lower_lb:
                fallback_models = [
                    "anthropic--claude-4.5-opus",
                    "anthropic--claude-4-opus",
                ]
            elif "haiku" in model_lower_lb:
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
        elif _is_gemini:
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


def select_subaccount_for_orchestration(proxy_config) -> str:
    """Round-robin select a subaccount for Orchestration V2 inference.

    Uses the wildcard "*" key in model_to_subaccounts to find all V2-enabled
    subaccounts and distributes load evenly across them.

    Args:
        proxy_config: The proxy configuration object.

    Returns:
        The selected subaccount name.

    Raises:
        ValueError: If no Orchestration V2 subaccounts are configured.
    """
    global _load_balance_counters

    subaccount_names = proxy_config.model_to_subaccounts.get("*", [])
    if not subaccount_names:
        raise ValueError(
            "No Orchestration V2 subaccounts configured. "
            "Ensure at least one subaccount has 'orchestration_url' set."
        )

    with _counters_lock:
        counter_key = "__orchestration_v2__"
        if counter_key not in _load_balance_counters:
            _load_balance_counters[counter_key] = 0
        idx = _load_balance_counters[counter_key] % len(subaccount_names)
        _load_balance_counters[counter_key] += 1

    selected = subaccount_names[idx]
    logger.info(
        "Orchestration V2 round-robin: selected subaccount '%s' (%d/%d)",
        selected,
        idx + 1,
        len(subaccount_names),
    )
    return selected


def reset_counters():
    """Reset all load balancing counters. Useful for testing."""
    global _load_balance_counters
    _load_balance_counters.clear()


def get_counters() -> dict:
    """Get the current load balancing counters. Useful for testing and debugging."""
    return _load_balance_counters.copy()
