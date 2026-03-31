"""Tests for orchestration deployment model name extraction in fetch_all_deployments()."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from utils.sdk_utils import fetch_all_deployments, _clear_client_caches_for_testing
from config.config_models import ServiceKey


@pytest.fixture(autouse=True)
def clear_caches():
    _clear_client_caches_for_testing()
    yield
    _clear_client_caches_for_testing()


@pytest.fixture
def service_key():
    return ServiceKey(
        client_id="test-client",
        client_secret="test-secret",
        auth_url="https://auth.test",
        api_url="https://api.test",
        identity_zone_id="test-zone",
    )


def _run_fetch(service_key, deployments_list):
    """Helper: run fetch_all_deployments with mocked API and cache."""
    with patch("utils.sdk_utils.AIAPIV2Client") as mock_client_cls:
        mock_client = Mock()
        mock_client_cls.return_value = mock_client

        mock_query_response = Mock()
        mock_query_response.resources = deployments_list
        mock_client.deployment.query.return_value = mock_query_response

        with patch("utils.sdk_utils.Cache") as mock_cache_cls:
            mock_cache = MagicMock()
            mock_cache.__enter__.return_value.get.return_value = None
            mock_cache_cls.return_value = mock_cache

            return fetch_all_deployments(service_key, force_refresh=True)


def _make_model_serving_deployment(dep_id="dep-model-1", url="https://model.example.com", model_name="anthropic--claude-4.5-sonnet"):
    """Build a mock model-serving deployment (has backend_details.model.name)."""
    dep = MagicMock()
    dep.id = dep_id
    dep.deployment_url = url
    dep.created_at = "2024-01-01"
    dep.details = {"resources": {"backend_details": {"model": {"name": model_name}}}}
    dep.configuration_name = "some-config"  # should be ignored when backend model is present
    return dep


def _make_orchestration_deployment(dep_id="dep-orch-1", url="https://orch.example.com", config_name="ail-auto-orchestration"):
    """Build a mock orchestration deployment (no backend_details.model.name, has configuration_name)."""
    dep = MagicMock()
    dep.id = dep_id
    dep.deployment_url = url
    dep.created_at = "2024-01-02"
    dep.details = {}  # no backend_details
    dep.configuration_name = config_name
    return dep


def _make_bare_deployment(dep_id="dep-bare-1", url="https://bare.example.com"):
    """Build a mock deployment with neither backend model name nor configuration_name."""
    dep = MagicMock()
    dep.id = dep_id
    dep.deployment_url = url
    dep.created_at = "2024-01-03"
    dep.details = {}
    dep.configuration_name = None
    return dep


# ---------------------------------------------------------------------------
# Scenario: Standard model-serving deployment unchanged
# ---------------------------------------------------------------------------

def test_model_serving_deployment_uses_backend_model_name(service_key):
    """backend_details.model.name takes precedence; configuration_name is ignored."""
    dep = _make_model_serving_deployment(model_name="anthropic--claude-4.5-sonnet")
    results = _run_fetch(service_key, [dep])

    assert len(results) == 1
    assert results[0]["model_name"] == "anthropic--claude-4.5-sonnet"


def test_model_serving_deployment_does_not_use_configuration_name(service_key):
    """When backend_details.model.name is set, configuration_name is never used."""
    dep = _make_model_serving_deployment(model_name="gpt-4o")
    dep.configuration_name = "should-not-appear"
    results = _run_fetch(service_key, [dep])

    assert results[0]["model_name"] == "gpt-4o"


# ---------------------------------------------------------------------------
# Scenario: Orchestration deployment uses configuration_name
# ---------------------------------------------------------------------------

def test_orchestration_deployment_uses_configuration_name(service_key):
    """Orchestration deployment with no backend model falls back to configuration_name."""
    dep = _make_orchestration_deployment(config_name="ail-auto-orchestration")
    results = _run_fetch(service_key, [dep])

    assert len(results) == 1
    assert results[0]["model_name"] == "ail-auto-orchestration"


def test_orchestration_deployment_appears_in_results(service_key):
    """Orchestration deployment is present in results list."""
    dep = _make_orchestration_deployment()
    results = _run_fetch(service_key, [dep])

    assert len(results) == 1
    assert results[0]["id"] == "dep-orch-1"


# ---------------------------------------------------------------------------
# Scenario: Deployment with neither backend model name nor configuration name
# ---------------------------------------------------------------------------

def test_bare_deployment_model_name_is_none(service_key):
    """Deployment with no backend model and no configuration_name gets model_name=None."""
    dep = _make_bare_deployment()
    results = _run_fetch(service_key, [dep])

    assert len(results) == 1
    assert results[0]["model_name"] is None


def test_bare_deployment_still_appears_in_results(service_key):
    """Deployment with no model name is still included — not silently dropped."""
    dep = _make_bare_deployment(dep_id="bare-no-name")
    results = _run_fetch(service_key, [dep])

    assert len(results) == 1
    assert results[0]["id"] == "bare-no-name"


# ---------------------------------------------------------------------------
# Mixed deployments in one call
# ---------------------------------------------------------------------------

def test_mixed_deployments_all_extracted_correctly(service_key):
    """All three deployment types in one API call are handled correctly."""
    model_dep = _make_model_serving_deployment(dep_id="d1", model_name="gpt-4o")
    orch_dep = _make_orchestration_deployment(dep_id="d2", config_name="my-orchestration")
    bare_dep = _make_bare_deployment(dep_id="d3")

    results = _run_fetch(service_key, [model_dep, orch_dep, bare_dep])

    assert len(results) == 3
    by_id = {r["id"]: r for r in results}
    assert by_id["d1"]["model_name"] == "gpt-4o"
    assert by_id["d2"]["model_name"] == "my-orchestration"
    assert by_id["d3"]["model_name"] is None
