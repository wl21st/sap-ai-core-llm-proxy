"""
Deployment auto-discovery for SAP AI Core LLM Proxy.

This module provides run_discovery() which is called at proxy startup (after config
loading, before ProxyGlobalContext.initialize()) to populate model_to_deployment_urls
from the SAP AI Core Deployments API for eligible subaccounts.

Eligibility:
- Explicit: subaccount has auto_discover=True
- Implicit: subaccount has no deployment_models AND no model_to_deployment_ids

Merge strategy: manually configured URLs take precedence.  Discovered URLs are
appended only when not already present.
"""

import logging

from config.config_models import ProxyConfig, SubAccountConfig
from config.config_parser import _auto_discover_deployments

logger = logging.getLogger(__name__)


def _is_eligible(subaccount: SubAccountConfig) -> bool:
    """Return True if the subaccount should have discovery run for it."""
    if subaccount.auto_discover:
        return True
    has_deployment_models = bool(subaccount.model_to_deployment_urls)
    has_deployment_ids = bool(subaccount.model_to_deployment_ids)
    return not has_deployment_models and not has_deployment_ids


def run_discovery(config: ProxyConfig) -> None:
    """Run deployment auto-discovery for eligible subaccounts.

    For each eligible subaccount, fetches all RUNNING deployments from the SAP AI
    Core Deployments API and merges discovered URLs into model_to_deployment_urls.
    Per-subaccount failures are logged as WARNING and do not abort startup.

    After discovery, rebuilds config.model_to_subaccounts to include newly
    registered models.

    Args:
        config: The loaded ProxyConfig whose subaccounts will be mutated in-place.
    """
    discovery_ran = False

    for name, subaccount in config.subaccounts.items():
        if not _is_eligible(subaccount):
            logger.debug(
                "Skipping auto-discovery for subaccount '%s' (manual config present, auto_discover=False)",
                name,
            )
            continue

        try:
            logger.info("Running auto-discovery for subaccount '%s'", name)
            _ = _auto_discover_deployments(subaccount)
            logger.info(
                "Auto-discovery complete for subaccount '%s': models now registered: %s",
                name,
                list(subaccount.model_to_deployment_urls.keys()),
            )
            discovery_ran = True
        except Exception as exc:
            logger.warning(
                "Auto-discovery failed for subaccount '%s': %s — continuing with manual config",
                name,
                exc,
            )

    # Rebuild model_to_subaccounts to include any newly discovered models
    if discovery_ran:
        config.model_to_subaccounts = {}
        for subaccount_name, subaccount in config.subaccounts.items():
            for model in subaccount.model_to_deployment_urls.keys():
                if model not in config.model_to_subaccounts:
                    config.model_to_subaccounts[model] = []
                config.model_to_subaccounts[model].append(subaccount_name)
        logger.info(
            "Rebuilt model_to_subaccounts after discovery: %s",
            list(config.model_to_subaccounts.keys()),
        )
