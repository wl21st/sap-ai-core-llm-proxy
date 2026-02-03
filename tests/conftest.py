"""Shared fixtures for unit tests."""

import pytest
from unittest.mock import Mock
from config.config_models import ServiceKey


@pytest.fixture
def mock_service_key():
    """Create a mock service key for testing."""
    key = Mock(spec=ServiceKey)
    key.client_id = "test-client-id"
    key.client_secret = "test-secret"
    key.api_url = "https://api.test.com"
    key.auth_url = "https://auth.test.com"
    key.identity_zone_id = "test-zone"
    return key


@pytest.fixture
def mock_deployment():
    """Create a mock deployment object."""
    deployment = Mock()
    deployment.id = "d123abc"
    deployment.deployment_url = "https://api.test.com/v2/inference/deployments/d123abc"
    deployment.created_at = "2026-01-01T00:00:00Z"
    deployment.modified_at = "2026-01-01T00:00:00Z"
    deployment.configuration_id = "config123"
    deployment.scenario_id = "scenario123"
    deployment.details = {
        "resources": {"backend_details": {"model": {"name": "claude-4.5-sonnet"}}}
    }
    return deployment


@pytest.fixture
def clean_cache():
    """Ensure cache is clean before and after test."""
    from utils.sdk_utils import clear_deployment_cache

    before_count = 0
    try:
        before_count = clear_deployment_cache()
    except:
        pass

    yield before_count

    after_count = 0
    try:
        after_count = clear_deployment_cache()
    except:
        pass
