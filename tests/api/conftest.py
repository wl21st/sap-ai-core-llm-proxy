"""
Pytest configuration for direct Bedrock API tests.

Fixtures for connecting directly to SAP AI Core Bedrock using account_key.json
from a proxy config file.

Config path resolution (first match wins):
  1. --config pytest CLI option
  2. SAP_AI_PROXY_CONFIG env var
  3. config.json in the project root (current working directory)
"""

import os
import pytest
from typing import Optional

from saip.config import ProxyConfig, SubAccountConfig
from saip.utils.logging_utils import get_server_logger

logger = get_server_logger(__name__)


def pytest_addoption(parser):
    parser.addoption(
        "--config",
        action="store",
        default=None,
        help="Path to proxy config.json (overrides SAP_AI_PROXY_CONFIG env var)",
    )


def pytest_configure(config):
    config_path = _resolve_config_path(config)
    print(f"\n[api tests] effective config: {os.path.abspath(config_path)}\n")


def _resolve_config_path(config: pytest.Config) -> str:
    """Resolve config path: CLI option > env var > project-root config.json."""
    cli = config.getoption("--config", default=None)
    if cli:
        return cli
    env = os.environ.get("SAP_AI_PROXY_CONFIG")
    if env:
        return env
    return "config.json"


@pytest.fixture(scope="session")
def proxy_config(pytestconfig) -> Optional[ProxyConfig]:
    """Load proxy config from the resolved config path."""
    config_path = _resolve_config_path(pytestconfig)
    try:
        from saip.config import load_proxy_config
        config = load_proxy_config(config_path)
        logger.info(f"Loaded proxy config from {config_path} with {len(config.subaccounts)} subaccounts")
        return config
    except Exception as e:
        logger.warning(f"Could not load SAP AI Core config from {config_path}: {e}")
        return None


@pytest.fixture(scope="session")
def first_subaccount(proxy_config) -> SubAccountConfig:
    """Get first available subaccount from saip.config. Fails if not configured."""
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

    def get_client(model: str, deployment_id: Optional[str] = None):
        """Get a Bedrock client for the given model."""
        from saip.utils.sdk_pool import get_bedrock_client

        # Map test model name to deployment name
        deployment_model = MODEL_MAPPING.get(model, model)

        # Find deployment URL for model
        deployment_urls = first_subaccount.model_to_deployment_urls.get(deployment_model, [])
        if not deployment_urls:
            raise ValueError(f"Model {model} (mapped to {deployment_model}) not configured in subaccount")

        if deployment_id is None:
            deployment_url = deployment_urls[0]
            # Extract deployment ID from URL (e.g., https://api.../deployments/abc123 -> abc123)
            deployment_id = deployment_url.split("/deployments/")[-1]

        # Get Bedrock client via SDK
        client = get_bedrock_client(
            sub_account_config=first_subaccount,
            model_name=deployment_model,
            deployment_id=deployment_id,
            ca_cert_bundle=None,
        )
        return client

    return get_client
