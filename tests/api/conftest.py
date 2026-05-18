"""
Pytest configuration for direct Bedrock API tests.

Fixtures for connecting directly to SAP AI Core Bedrock using account_key.json
from ~/.aicore/config.json
"""

import json
import os
import pytest
from pathlib import Path
from typing import Optional

from config import ProxyConfig, SubAccountConfig
from utils.logging_utils import get_server_logger
from utils.sdk_pool import get_bedrock_client
from gen_ai_hub.proxy.native.amazon.clients import ClientWrapper

logger = get_server_logger(__name__)


@pytest.fixture(scope="session")
def proxy_config() -> Optional[ProxyConfig]:
    """Load proxy config from ~/.aicore/config.json (account_key.json)."""
    try:
        config = ProxyConfig.load_from_file()
        logger.info(f"Loaded proxy config with {len(config.subaccounts)} subaccounts")
        return config
    except Exception as e:
        logger.warning(f"Could not load SAP AI Core config: {e}")
        return None


@pytest.fixture(scope="session")
def first_subaccount(proxy_config) -> Optional[SubAccountConfig]:
    """Get first available subaccount from config."""
    if not proxy_config or not proxy_config.subaccounts:
        return None
    subaccount_name = next(iter(proxy_config.subaccounts.keys()))
    return proxy_config.subaccounts[subaccount_name]


@pytest.fixture
def bedrock_client_factory(first_subaccount):
    """Factory fixture to get Bedrock clients for different models."""
    if not first_subaccount:
        pytest.skip("No SAP AI Core subaccount configured")

    def get_client(model: str, deployment_id: Optional[str] = None) -> ClientWrapper:
        """Get a Bedrock client for the given model."""
        # Find deployment URL for model
        deployment_urls = first_subaccount.deployment_models.get(model, [])
        if not deployment_urls:
            pytest.skip(f"Model {model} not configured in subaccount")

        if deployment_id is None:
            deployment_id = deployment_urls[0]

        # Get Bedrock client via SDK
        client = get_bedrock_client(
            sub_account_config=first_subaccount,
            model_name=model,
            deployment_id=deployment_id,
            ca_cert_bundle=None,
        )
        return client

    return get_client
