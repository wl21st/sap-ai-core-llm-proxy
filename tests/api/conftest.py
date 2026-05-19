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
    """Load proxy config from project config.json."""
    try:
        from config import load_proxy_config
        config_path = Path(__file__).parent.parent.parent / "config.json"
        config = load_proxy_config(str(config_path))
        logger.info(f"Loaded proxy config with {len(config.subaccounts)} subaccounts")
        return config
    except Exception as e:
        logger.warning(f"Could not load SAP AI Core config: {e}")
        return None


@pytest.fixture(scope="session")
def first_subaccount(proxy_config) -> SubAccountConfig:
    """Get first available subaccount from config. Fails if not configured."""
    if not proxy_config or not proxy_config.subaccounts:
        pytest.fail("No SAP AI Core config found. Check config.json and service_key_json path.")
    subaccount_name = next(iter(proxy_config.subaccounts.keys()))
    return proxy_config.subaccounts[subaccount_name]


@pytest.fixture
def bedrock_client_factory(first_subaccount):
    """Factory fixture to get Bedrock clients for different models."""
    if not first_subaccount:
        pytest.fail("No SAP AI Core subaccount available")

    # Map test model names to SAP AI Core deployment names
    MODEL_MAPPING = {
        "sonnet-4.6": "anthropic--claude-4.6-sonnet",
        "opus-4.7": "anthropic--claude-4.7-opus",
        "haiku-4.5": "anthropic--claude-4.5-haiku",
    }

    def get_client(model: str, deployment_id: Optional[str] = None) -> ClientWrapper:
        """Get a Bedrock client for the given model."""
        # Map test model name to deployment name
        deployment_model = MODEL_MAPPING.get(model, model)

        # Find deployment URL for model
        deployment_urls = first_subaccount.model_to_deployment_urls.get(deployment_model, [])
        if not deployment_urls:
            raise ValueError(f"Model {model} (mapped to {deployment_model}) not configured in subaccount")

        if deployment_id is None:
            deployment_id = deployment_urls[0]

        # Get Bedrock client via SDK
        client = get_bedrock_client(
            sub_account_config=first_subaccount,
            model_name=deployment_model,
            deployment_id=deployment_id,
            ca_cert_bundle=None,
        )
        return client

    return get_client
