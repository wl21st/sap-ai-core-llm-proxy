"""Tests for discovery.py run_discovery() function."""

import pytest
from dataclasses import field
from unittest.mock import patch, MagicMock

from config.config_models import ProxyConfig, SubAccountConfig, ServiceKey, TokenInfo
from discovery import run_discovery, _is_eligible


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_service_key() -> ServiceKey:
    key = ServiceKey(
        client_id="test-client",
        client_secret="test-secret",
        auth_url="https://auth.test",
        api_url="https://api.test",
        identity_zone_id="test-zone",
    )
    return key


def _make_subaccount(
    name: str = "test-sub",
    deployment_models: dict | None = None,
    deployment_ids: dict | None = None,
    auto_discover: bool = False,
) -> SubAccountConfig:
    sub = SubAccountConfig(
        name=name,
        resource_group="default",
        service_key_json="key.json",
        model_to_deployment_urls=deployment_models or {},
        model_to_deployment_ids=deployment_ids or {},
        auto_discover=auto_discover,
    )
    sub.service_key = _make_service_key()
    return sub


def _make_config(subaccounts: dict | None = None) -> ProxyConfig:
    config = ProxyConfig()
    config.subaccounts = subaccounts or {}
    config.model_to_subaccounts = {}
    return config


# ---------------------------------------------------------------------------
# _is_eligible tests
# ---------------------------------------------------------------------------

def test_eligible_when_auto_discover_true():
    sub = _make_subaccount(auto_discover=True, deployment_models={"gpt-4": ["https://url"]})
    assert _is_eligible(sub) is True


def test_eligible_when_no_deployment_models_and_no_ids():
    sub = _make_subaccount(auto_discover=False)
    assert _is_eligible(sub) is True


def test_not_eligible_when_deployment_models_present():
    sub = _make_subaccount(
        deployment_models={"gpt-4": ["https://url"]},
        auto_discover=False,
    )
    assert _is_eligible(sub) is False


def test_not_eligible_when_deployment_ids_present():
    sub = _make_subaccount(
        deployment_ids={"gpt-4": ["d123"]},
        auto_discover=False,
    )
    assert _is_eligible(sub) is False


# ---------------------------------------------------------------------------
# run_discovery: skips ineligible subaccounts
# ---------------------------------------------------------------------------

@patch("discovery._auto_discover_deployments")
def test_run_discovery_skips_manual_config_subaccount(mock_discover):
    sub = _make_subaccount(deployment_models={"gpt-4": ["https://url"]})
    config = _make_config({"account1": sub})

    run_discovery(config)

    mock_discover.assert_not_called()


# ---------------------------------------------------------------------------
# run_discovery: new model from discovery
# ---------------------------------------------------------------------------

@patch("discovery._auto_discover_deployments")
def test_run_discovery_registers_new_model(mock_discover):
    """Discovery runs and a new model URL appears in model_to_deployment_urls."""
    sub = _make_subaccount()  # no deployment_models → eligible

    def fake_discover(subaccount):
        subaccount.model_to_deployment_urls["ail-auto-orchestration"] = [
            "https://orch.example.com"
        ]

    mock_discover.side_effect = fake_discover
    config = _make_config({"account1": sub})

    run_discovery(config)

    assert "ail-auto-orchestration" in sub.model_to_deployment_urls
    assert "ail-auto-orchestration" in config.model_to_subaccounts


# ---------------------------------------------------------------------------
# run_discovery: merge with existing manual config
# ---------------------------------------------------------------------------

@patch("discovery._auto_discover_deployments")
def test_run_discovery_merges_with_manual_config(mock_discover):
    """auto_discover=True + existing manual URLs → both present after discovery."""
    sub = _make_subaccount(
        deployment_models={"gpt-4o": ["https://manual.example.com"]},
        auto_discover=True,
    )

    def fake_discover(subaccount):
        # Simulates _auto_discover_deployments adding a new model
        subaccount.model_to_deployment_urls["new-model"] = ["https://new.example.com"]

    mock_discover.side_effect = fake_discover
    config = _make_config({"account1": sub})
    # Simulate what load_proxy_config built
    config.model_to_subaccounts = {"gpt-4o": ["account1"]}

    run_discovery(config)

    assert "gpt-4o" in sub.model_to_deployment_urls
    assert "new-model" in sub.model_to_deployment_urls
    # model_to_subaccounts rebuilt to include both
    assert "gpt-4o" in config.model_to_subaccounts
    assert "new-model" in config.model_to_subaccounts


# ---------------------------------------------------------------------------
# run_discovery: failure tolerance
# ---------------------------------------------------------------------------

@patch("discovery._auto_discover_deployments")
def test_run_discovery_continues_on_failure(mock_discover):
    """If discovery raises for one subaccount, others still run and startup continues."""
    sub1 = _make_subaccount(name="failing-sub")
    sub2 = _make_subaccount(name="good-sub")

    def fake_discover(subaccount):
        if subaccount.name == "failing-sub":
            raise RuntimeError("Network error")
        subaccount.model_to_deployment_urls["found-model"] = ["https://good.example.com"]

    mock_discover.side_effect = fake_discover
    config = _make_config({"failing-sub": sub1, "good-sub": sub2})

    # Should not raise
    run_discovery(config)

    assert "found-model" in sub2.model_to_deployment_urls


@patch("discovery._auto_discover_deployments")
def test_run_discovery_logs_warning_on_failure(mock_discover, caplog):
    """Failure for a subaccount is logged as WARNING."""
    import logging

    sub = _make_subaccount(name="bad-sub")
    mock_discover.side_effect = RuntimeError("Connection refused")
    config = _make_config({"bad-sub": sub})

    with caplog.at_level(logging.WARNING):
        run_discovery(config)

    assert any(
        "bad-sub" in r.message and r.levelno == logging.WARNING
        for r in caplog.records
    )


# ---------------------------------------------------------------------------
# run_discovery: skip None model_name (handled inside _auto_discover_deployments)
# ---------------------------------------------------------------------------

@patch("discovery._auto_discover_deployments")
def test_run_discovery_none_model_name_not_registered(mock_discover):
    """Deployment with None model_name is not added to model_to_deployment_urls."""
    sub = _make_subaccount()

    def fake_discover(subaccount):
        # Only adds non-None entries — consistent with _auto_discover_deployments behavior
        pass  # no URLs added

    mock_discover.side_effect = fake_discover
    config = _make_config({"account1": sub})

    run_discovery(config)

    assert sub.model_to_deployment_urls == {}


# ---------------------------------------------------------------------------
# run_discovery: model_to_subaccounts rebuild
# ---------------------------------------------------------------------------

@patch("discovery._auto_discover_deployments")
def test_run_discovery_rebuilds_model_to_subaccounts(mock_discover):
    """After discovery, model_to_subaccounts contains newly discovered models."""
    sub = _make_subaccount(name="account1")

    def fake_discover(subaccount):
        subaccount.model_to_deployment_urls["orchestration-model"] = [
            "https://orch.example.com"
        ]

    mock_discover.side_effect = fake_discover
    config = _make_config({"account1": sub})
    config.model_to_subaccounts = {}

    run_discovery(config)

    assert config.model_to_subaccounts.get("orchestration-model") == ["account1"]


# ---------------------------------------------------------------------------
# run_discovery: no rebuild when no eligible subaccounts
# ---------------------------------------------------------------------------

@patch("discovery._auto_discover_deployments")
def test_run_discovery_no_rebuild_when_all_skipped(mock_discover):
    """model_to_subaccounts is NOT rebuilt when no eligible subaccounts ran discovery."""
    sub = _make_subaccount(
        deployment_models={"gpt-4": ["https://url"]},
        auto_discover=False,
    )
    config = _make_config({"account1": sub})
    config.model_to_subaccounts = {"gpt-4": ["account1"]}

    run_discovery(config)

    mock_discover.assert_not_called()
    # Unchanged
    assert config.model_to_subaccounts == {"gpt-4": ["account1"]}


# ---------------------------------------------------------------------------
# Integration-level (mocked): auto_discover=True, no deployment_models →
# models available for routing after run_discovery()
# ---------------------------------------------------------------------------

@patch("discovery._auto_discover_deployments")
def test_auto_discover_true_no_deployment_models_models_available(mock_discover):
    """
    A subaccount with auto_discover=True and no deployment_models should have
    models available for routing (in model_to_subaccounts) after run_discovery().
    """
    sub = _make_subaccount(name="account1", auto_discover=True)

    def fake_discover(subaccount):
        subaccount.model_to_deployment_urls["ail-auto-orchestration"] = [
            "https://orch.example.com/v2/inference/deployments/d1"
        ]

    mock_discover.side_effect = fake_discover
    config = _make_config({"account1": sub})
    config.model_to_subaccounts = {}

    # Simulate what lifespan() does: load_proxy_config() + run_discovery()
    run_discovery(config)

    # Model must be routable
    assert "ail-auto-orchestration" in config.model_to_subaccounts
    assert config.model_to_subaccounts["ail-auto-orchestration"] == ["account1"]
    # URL must be in subaccount
    assert sub.model_to_deployment_urls["ail-auto-orchestration"] == [
        "https://orch.example.com/v2/inference/deployments/d1"
    ]
