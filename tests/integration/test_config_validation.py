import pytest
from unittest.mock import MagicMock, patch
import logging
from config.config_models import SubAccountConfig, ServiceKey
from config.config_parser import _build_mapping_for_subaccount
from utils.exceptions import ConfigValidationError


def test_validation_warning(caplog):
    """Test that validation mismatch logs a warning."""
    # Setup logger capture
    caplog.set_level(logging.WARNING)

    # Setup config
    sub_config = SubAccountConfig(
        name="test_sub",
        service_key_json="dummy.json",
        model_to_deployment_ids={"gpt-4": ["d123"]},
        resource_group="default",
        model_to_deployment_urls={},
        # We need to manually set service_key since we are calling _build... directly
        # and bypassing _load_service_key...
    )
    sub_config.service_key = ServiceKey(
        client_id="c",
        client_secret="s",
        auth_url="a",
        api_url="u",
        identity_zone_id="i",
    )

    # Mock fetch_all_deployments to return a mismatch
    # d123 -> gemini-pro (Family mismatch for gpt-4)
    with patch("config.config_parser.fetch_all_deployments") as mock_fetch_all:
        mock_fetch_all.return_value = [
            {"id": "d123", "url": "https://url/d123", "model_name": "gemini-pro"}
        ]

        # Also need to mock fetch_deployment_url to avoid network call in the loop
        with patch("config.config_parser.fetch_deployment_url") as mock_fetch_url:
            mock_fetch_url.return_value = "https://url/d123"

            _build_mapping_for_subaccount(sub_config)

            # Assert warning
            assert "Configuration mismatch" in caplog.text
            assert "gpt-4" in caplog.text
            assert "gemini-pro" in caplog.text
            assert "Family mismatch" in caplog.text


def test_validation_success(caplog):
    """Test that valid configuration does NOT log a warning."""
    caplog.set_level(logging.WARNING)

    sub_config = SubAccountConfig(
        name="test_sub_valid",
        service_key_json="dummy.json",
        model_to_deployment_ids={"gpt-4": ["d123"]},
        resource_group="default",
        model_to_deployment_urls={},
    )
    sub_config.service_key = ServiceKey(
        client_id="c",
        client_secret="s",
        auth_url="a",
        api_url="u",
        identity_zone_id="i",
    )

    with patch("config.config_parser.fetch_all_deployments") as mock_fetch_all:
        mock_fetch_all.return_value = [
            {"id": "d123", "url": "https://url/d123", "model_name": "gpt-4"}
        ]

        with patch("config.config_parser.fetch_deployment_url") as mock_fetch_url:
            mock_fetch_url.return_value = "https://url/d123"

            _build_mapping_for_subaccount(sub_config)

            # Assert NO warning
            assert "Configuration mismatch" not in caplog.text


def test_deployment_not_found_warning(caplog):
    """Test warning when deployment ID is not found in discovery."""
    caplog.set_level(logging.WARNING)

    sub_config = SubAccountConfig(
        name="test_sub_missing",
        service_key_json="dummy.json",
        model_to_deployment_ids={"gpt-4": ["d999"]},
        resource_group="default",
        model_to_deployment_urls={},
    )
    sub_config.service_key = ServiceKey(
        client_id="c",
        client_secret="s",
        auth_url="a",
        api_url="u",
        identity_zone_id="i",
    )

    with patch("config.config_parser.fetch_all_deployments") as mock_fetch_all:
        # Discovery succeeds but returns unrelated deployment
        mock_fetch_all.return_value = [
            {"id": "d123", "url": "https://url/d123", "model_name": "gpt-4"}
        ]

        with patch("config.config_parser.fetch_deployment_url") as mock_fetch_url:
            mock_fetch_url.return_value = "https://url/d999"

            _build_mapping_for_subaccount(sub_config)

            # Assert warning
            assert (
                "Configuration warning: Deployment 'd999' mapped to model 'gpt-4' not found in subaccount"
                in caplog.text
            )


def test_config_load_auth_failure(tmp_path):
    """Test that config loading fails fast on authentication error."""
    import json

    # Create temporary service key file
    service_key_file = tmp_path / "service_key.json"
    service_key_data = {
        "clientid": "test-client",
        "clientsecret": "test-secret",
        "url": "https://auth.test.com",
        "identityzoneid": "test-zone",
        "serviceurls": {"AI_API_URL": "https://api.test.com"},
    }
    service_key_file.write_text(json.dumps(service_key_data))

    # Create config file
    config_file = tmp_path / "config.json"
    config_data = {
        "subAccounts": {
            "test-account": {
                "resource_group": "default",
                "service_key_json": str(service_key_file),
                "deployment_models": {},
            }
        }
    }
    config_file.write_text(json.dumps(config_data))

    from config.config_parser import load_proxy_config
    from utils.exceptions import AuthenticationError

    with patch("config.config_parser.fetch_all_deployments") as mock_fetch:
        mock_fetch.side_effect = AuthenticationError("Invalid credentials")

        with pytest.raises((ConfigValidationError, AuthenticationError)) as exc_info:
            load_proxy_config(str(config_file))

        assert (
            "authentication" in str(exc_info.value).lower()
            or "credentials" in str(exc_info.value).lower()
        )


def test_config_load_network_failure(tmp_path):
    """Test that config loading fails fast on network error."""
    import json

    # Create temporary service key file
    service_key_file = tmp_path / "service_key.json"
    service_key_data = {
        "clientid": "test-client",
        "clientsecret": "test-secret",
        "url": "https://auth.test.com",
        "identityzoneid": "test-zone",
        "serviceurls": {"AI_API_URL": "https://api.test.com"},
    }
    service_key_file.write_text(json.dumps(service_key_data))

    # Create config file
    config_file = tmp_path / "config.json"
    config_data = {
        "subAccounts": {
            "test-account": {
                "resource_group": "default",
                "service_key_json": str(service_key_file),
                "deployment_models": {},
            }
        }
    }
    config_file.write_text(json.dumps(config_data))

    from config.config_parser import load_proxy_config
    import requests

    with patch("config.config_parser.fetch_all_deployments") as mock_fetch:
        mock_fetch.side_effect = requests.exceptions.ConnectionError(
            "Network unreachable"
        )

        with pytest.raises(ConfigValidationError) as exc_info:
            load_proxy_config(str(config_file))

        assert (
            "network" in str(exc_info.value).lower()
            or "connection" in str(exc_info.value).lower()
        )


def test_config_load_invalid_deployment_id(tmp_path):
    """Test that config loading fails on invalid deployment ID."""
    import json

    # Create temporary service key file
    service_key_file = tmp_path / "service_key.json"
    service_key_data = {
        "clientid": "test-client",
        "clientsecret": "test-secret",
        "url": "https://auth.test.com",
        "identityzoneid": "test-zone",
        "serviceurls": {"AI_API_URL": "https://api.test.com"},
    }
    service_key_file.write_text(json.dumps(service_key_data))

    # Create config file with invalid deployment ID
    config_file = tmp_path / "config.json"
    config_data = {
        "subAccounts": {
            "test-account": {
                "resource_group": "default",
                "service_key_json": str(service_key_file),
                "deployment_ids": {"gpt-4o": ["invalid-deployment-id"]},
            }
        }
    }
    config_file.write_text(json.dumps(config_data))

    from config.config_parser import load_proxy_config

    with patch("config.config_parser.extract_deployment_id") as mock_extract:
        mock_extract.side_effect = ValueError("Invalid deployment ID format")

        # This should raise ConfigValidationError during config parsing
        with pytest.raises(ConfigValidationError) as exc_info:
            load_proxy_config(str(config_file))

        assert "deployment" in str(exc_info.value).lower()
