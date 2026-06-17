"""Tests for auto_discover field in SubAccountConfig and config parsing."""

import json
import os
import tempfile
from unittest.mock import patch, MagicMock

import pytest

from config.config_models import SubAccountConfig, TokenInfo
from config.config_parser import load_proxy_config


# ---------------------------------------------------------------------------
# SubAccountConfig dataclass default
# ---------------------------------------------------------------------------

def test_subaccount_config_auto_discover_defaults_false():
    """SubAccountConfig.auto_discover defaults to False."""
    sub = SubAccountConfig(
        name="test",
        resource_group="default",
        service_key_json="key.json",
        model_to_deployment_urls={},
    )
    assert sub.auto_discover is False


def test_subaccount_config_auto_discover_explicit_true():
    """SubAccountConfig.auto_discover can be set to True."""
    sub = SubAccountConfig(
        name="test",
        resource_group="default",
        service_key_json="key.json",
        model_to_deployment_urls={},
        auto_discover=True,
    )
    assert sub.auto_discover is True


# ---------------------------------------------------------------------------
# Helpers to build a minimal config.json and service key on disk
# ---------------------------------------------------------------------------

def _write_service_key(dir_path: str, filename: str = "key.json") -> str:
    key_path = os.path.join(dir_path, filename)
    key_data = {
        "clientid": "client-id",
        "clientsecret": "client-secret",
        "url": "https://auth.example.com",
        "identityzoneid": "zone-id",
        "serviceurls": {"AI_API_URL": "https://api.example.com"},
    }
    with open(key_path, "w") as f:
        json.dump(key_data, f)
    return key_path


def _write_config(dir_path: str, sub_accounts: dict, filename: str = "config.json") -> str:
    config_path = os.path.join(dir_path, filename)
    config_data = {
        "secret_authentication_tokens": ["tok"],
        "subAccounts": sub_accounts,
    }
    with open(config_path, "w") as f:
        json.dump(config_data, f)
    return config_path


# ---------------------------------------------------------------------------
# load_proxy_config: auto_discover field parsing
# ---------------------------------------------------------------------------

def _mock_build_mapping(sub):
    """No-op replacement for _build_mapping_for_subaccount to avoid network calls."""
    pass


@patch("config.config_parser._build_mapping_for_subaccount", side_effect=_mock_build_mapping)
def test_load_proxy_config_auto_discover_true(mock_build):
    with tempfile.TemporaryDirectory() as tmpdir:
        key_path = _write_service_key(tmpdir)
        config_path = _write_config(
            tmpdir,
            {
                "account1": {
                    "resource_group": "default",
                    "service_key_json": key_path,
                    "auto_discover": True,
                }
            },
        )
        config = load_proxy_config(config_path)

    assert config.subaccounts["account1"].auto_discover is True


@patch("config.config_parser._build_mapping_for_subaccount", side_effect=_mock_build_mapping)
def test_load_proxy_config_auto_discover_false_explicit(mock_build):
    with tempfile.TemporaryDirectory() as tmpdir:
        key_path = _write_service_key(tmpdir)
        config_path = _write_config(
            tmpdir,
            {
                "account1": {
                    "resource_group": "default",
                    "service_key_json": key_path,
                    "auto_discover": False,
                }
            },
        )
        config = load_proxy_config(config_path)

    assert config.subaccounts["account1"].auto_discover is False


@patch("config.config_parser._build_mapping_for_subaccount", side_effect=_mock_build_mapping)
def test_load_proxy_config_auto_discover_absent_defaults_false(mock_build):
    """Backward compat: when auto_discover is absent from JSON, defaults to False."""
    with tempfile.TemporaryDirectory() as tmpdir:
        key_path = _write_service_key(tmpdir)
        config_path = _write_config(
            tmpdir,
            {
                "account1": {
                    "resource_group": "default",
                    "service_key_json": key_path,
                    # no auto_discover key
                }
            },
        )
        config = load_proxy_config(config_path)

    assert config.subaccounts["account1"].auto_discover is False


@patch("config.config_parser._build_mapping_for_subaccount", side_effect=_mock_build_mapping)
def test_load_proxy_config_with_deployment_models_no_auto_discover(mock_build):
    """Subaccount with deployment_models and no auto_discover is backward compatible."""
    with tempfile.TemporaryDirectory() as tmpdir:
        key_path = _write_service_key(tmpdir)
        config_path = _write_config(
            tmpdir,
            {
                "account1": {
                    "resource_group": "default",
                    "service_key_json": key_path,
                    "deployment_models": {"gpt-4": ["https://api.example.com/v2/inference/deployments/d1"]},
                }
            },
        )
        config = load_proxy_config(config_path)

    sub = config.subaccounts["account1"]
    assert sub.auto_discover is False
    assert "gpt-4" in sub.model_to_deployment_urls
