"""Integration tests for config validation — Orchestration V2 schema.

These tests validate config loading behavior with the new orchestration_url-based schema.
The legacy _build_mapping_for_subaccount, _resolve_deployment_ids, and
_extract_deployment_ids_from_urls functions have been removed; these tests cover
the new auto-discovery and validation flows.
"""

import json
import logging
import pytest
from unittest.mock import patch

from config.config_models import SubAccountConfig, ServiceKey
from utils.exceptions import ConfigValidationError


# ---------------------------------------------------------------------------
# Auto-discovery tests
# ---------------------------------------------------------------------------


def test_auto_discover_orchestration_url_success(caplog):
    """Auto-discovery finds the orchestration deployment URL when available."""
    caplog.set_level(logging.INFO)

    sub_config = SubAccountConfig(
        name="test_sub",
        service_key_json="dummy.json",
        resource_group="default",
    )
    sub_config.service_key = ServiceKey(
        client_id="c",
        client_secret="s",
        auth_url="a",
        api_url="u",
        identity_zone_id="i",
    )

    from config.config_parser import _auto_discover_orchestration_url

    orch_url = "https://api.ai.com/v2/inference/deployments/orchestration123"

    with patch("config.config_parser.fetch_all_deployments") as mock_fetch:
        mock_fetch.return_value = [
            {"id": "orch123", "url": orch_url, "model_name": "orchestration"},
            {"id": "gpt123", "url": "https://api.ai.com/v2/gpt", "model_name": "gpt-4o"},
        ]

        discovered = _auto_discover_orchestration_url(sub_config)

    assert discovered == orch_url


def test_auto_discover_orchestration_url_not_found(caplog):
    """Auto-discovery returns None when no orchestration deployment exists."""
    caplog.set_level(logging.WARNING)

    sub_config = SubAccountConfig(
        name="test_sub",
        service_key_json="dummy.json",
        resource_group="default",
    )
    sub_config.service_key = ServiceKey(
        client_id="c",
        client_secret="s",
        auth_url="a",
        api_url="u",
        identity_zone_id="i",
    )

    from config.config_parser import _auto_discover_orchestration_url

    with patch("config.config_parser.fetch_all_deployments") as mock_fetch:
        mock_fetch.return_value = [
            {"id": "gpt123", "url": "https://api.ai.com/v2/gpt", "model_name": "gpt-4o"},
        ]

        discovered = _auto_discover_orchestration_url(sub_config)

    assert discovered is None
    assert "No orchestration service deployment found" in caplog.text


def test_auto_discover_handles_fetch_error(caplog):
    """Auto-discovery returns None gracefully when fetch_all_deployments fails."""
    caplog.set_level(logging.WARNING)

    sub_config = SubAccountConfig(
        name="test_sub",
        service_key_json="dummy.json",
        resource_group="default",
    )
    sub_config.service_key = ServiceKey(
        client_id="c",
        client_secret="s",
        auth_url="a",
        api_url="u",
        identity_zone_id="i",
    )

    from config.config_parser import _auto_discover_orchestration_url

    with patch("config.config_parser.fetch_all_deployments") as mock_fetch:
        mock_fetch.side_effect = ConnectionError("Network error")

        discovered = _auto_discover_orchestration_url(sub_config)

    assert discovered is None


# ---------------------------------------------------------------------------
# Full config loading tests with new schema
# ---------------------------------------------------------------------------


def test_config_load_with_orchestration_url(tmp_path):
    """Config loads successfully with explicit orchestration_url."""
    service_key_file = tmp_path / "service_key.json"
    service_key_data = {
        "clientid": "test-client",
        "clientsecret": "test-secret",
        "url": "https://auth.test.com",
        "identityzoneid": "test-zone",
        "serviceurls": {"AI_API_URL": "https://api.test.com"},
    }
    service_key_file.write_text(json.dumps(service_key_data))

    config_file = tmp_path / "config.json"
    orch_url = "https://api.ai.test.com/v2/inference/deployments/orch123"
    config_data = {
        "subAccounts": {
            "test-account": {
                "resource_group": "default",
                "service_key_json": str(service_key_file),
                "orchestration_url": orch_url,
            }
        }
    }
    config_file.write_text(json.dumps(config_data))

    from config.config_parser import load_proxy_config

    config = load_proxy_config(str(config_file))

    assert "test-account" in config.subaccounts
    assert config.subaccounts["test-account"].orchestration_url == orch_url
    assert "*" in config.model_to_subaccounts
    assert "test-account" in config.model_to_subaccounts["*"]


def test_config_load_auto_discovers_orchestration_url(tmp_path):
    """Config loading auto-discovers orchestration_url when not explicitly set."""
    service_key_file = tmp_path / "service_key.json"
    service_key_data = {
        "clientid": "test-client",
        "clientsecret": "test-secret",
        "url": "https://auth.test.com",
        "identityzoneid": "test-zone",
        "serviceurls": {"AI_API_URL": "https://api.test.com"},
    }
    service_key_file.write_text(json.dumps(service_key_data))

    config_file = tmp_path / "config.json"
    config_data = {
        "subAccounts": {
            "test-account": {
                "resource_group": "default",
                "service_key_json": str(service_key_file),
                # No orchestration_url — should auto-discover
            }
        }
    }
    config_file.write_text(json.dumps(config_data))

    from config.config_parser import load_proxy_config

    orch_url = "https://api.ai.test.com/v2/inference/deployments/orch999"

    with patch("config.config_parser.fetch_all_deployments") as mock_fetch:
        mock_fetch.return_value = [
            {"id": "orch999", "url": orch_url, "model_name": "orchestration"},
        ]

        config = load_proxy_config(str(config_file))

    assert config.subaccounts["test-account"].orchestration_url == orch_url


def test_config_load_fails_without_orchestration_url_and_no_discovery(tmp_path):
    """Config loading raises ConfigValidationError when no orchestration URL can be found."""
    service_key_file = tmp_path / "service_key.json"
    service_key_data = {
        "clientid": "test-client",
        "clientsecret": "test-secret",
        "url": "https://auth.test.com",
        "identityzoneid": "test-zone",
        "serviceurls": {"AI_API_URL": "https://api.test.com"},
    }
    service_key_file.write_text(json.dumps(service_key_data))

    config_file = tmp_path / "config.json"
    config_data = {
        "subAccounts": {
            "test-account": {
                "resource_group": "default",
                "service_key_json": str(service_key_file),
                # No orchestration_url, and discovery returns nothing
            }
        }
    }
    config_file.write_text(json.dumps(config_data))

    from config.config_parser import load_proxy_config

    with patch("config.config_parser.fetch_all_deployments") as mock_fetch:
        mock_fetch.return_value = []  # No deployments found

        with pytest.raises(ConfigValidationError) as exc_info:
            load_proxy_config(str(config_file))

    assert "orchestration_url" in str(exc_info.value).lower() or "no orchestration" in str(exc_info.value).lower()


def test_config_load_emits_deprecation_warning_for_old_fields(tmp_path):
    """Config loading emits DeprecationWarning when deployment_ids or deployment_models present."""
    import warnings

    service_key_file = tmp_path / "service_key.json"
    service_key_data = {
        "clientid": "c",
        "clientsecret": "s",
        "url": "https://auth.test.com",
        "identityzoneid": "z",
        "serviceurls": {"AI_API_URL": "https://api.test.com"},
    }
    service_key_file.write_text(json.dumps(service_key_data))

    orch_url = "https://api.ai.test.com/v2/inference/deployments/orch1"
    config_file = tmp_path / "config.json"
    config_data = {
        "subAccounts": {
            "test-account": {
                "resource_group": "default",
                "service_key_json": str(service_key_file),
                "orchestration_url": orch_url,
                "deployment_ids": {"gpt-4o": ["d123"]},  # deprecated
            }
        }
    }
    config_file.write_text(json.dumps(config_data))

    from config.config_parser import load_proxy_config

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        load_proxy_config(str(config_file))

    deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
    assert len(deprecation_warnings) >= 1
    assert "deployment_ids" in str(deprecation_warnings[0].message)
