#!/usr/bin/env python3
"""
Utility script to inspect SAP AI Core deployments and their backend model names.
Usage: python inspect_deployments.py [-c config.json]
"""

import argparse
import logging
import sys
from typing import Any

from config.config_parser import load_proxy_config
from config import ProxyConfig
from utils.sdk_utils import fetch_all_deployments
from proxy_helpers import MODEL_ALIASES

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def inspect_subaccount(name: str, sub_config: Any):
    """Inspect deployments for a single subaccount.

    Args:
        name: Subaccount name
        sub_config: Subaccount configuration
    """
    print(f"\n--- Subaccount: {name} ---")
    print(f"Resource Group: {sub_config.resource_group}")

    try:
        deployments = fetch_all_deployments(
            service_key=sub_config.service_key,
            resource_group=sub_config.resource_group,
            force_refresh=True
        )

        if not deployments:
            print("  No deployments found.")
            return

        # Print table header
        print(
            f"\n  {'DEPLOYMENT ID':<35} | {'BACKEND MODEL':<30} | {'ALIASES':<30} | {'URL'}"
        )
        print(f"  {'-' * 35} | {'-' * 30} | {'-' * 30} | {'-' * 10}")

        for dep in deployments:
            dep_id = dep.get("id", "N/A")
            backend_model = dep.get("model_name", "N/A") or "Unknown"
            url = dep.get("url", "N/A")

            # Find aliases
            aliases = []
            if backend_model in MODEL_ALIASES:
                aliases = MODEL_ALIASES[backend_model]

            alias_str = ", ".join(aliases) if aliases else ""

            print(f"  {dep_id:<35} | {backend_model:<30} | {alias_str:<30} | {url}")

    except Exception as e:
        logger.error(f"  Failed to inspect subaccount {name}: {e}")


def main():
    parser = argparse.ArgumentParser(description="Inspect SAP AI Core deployments")
    parser.add_argument(
        "-c", "--config", default="config.json", help="Path to config.json"
    )
    args = parser.parse_args()

    # Initialize basic logging (quieting external libs)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("ai_core_sdk").setLevel(logging.WARNING)

    try:
        print(f"Loading configuration from {args.config}...")
        config: ProxyConfig = load_proxy_config(args.config)

        print(f"Found {len(config.subaccounts)} subaccounts.")

        for name, sub_config in config.subaccounts.items():
            inspect_subaccount(name, sub_config)

    except FileNotFoundError:
        logger.error(f"Config file not found: {args.config}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
