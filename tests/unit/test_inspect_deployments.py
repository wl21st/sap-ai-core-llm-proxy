import pytest
from unittest.mock import Mock, patch, MagicMock
from inspect_deployments import inspect_subaccount
from config import SubAccountConfig, ServiceKey


@pytest.fixture
def mock_sub_config():
    service_key = ServiceKey(
        client_id="test-client",
        client_secret="test-secret",
        auth_url="https://auth.test",
        api_url="https://api.test",
        identity_zone_id="test-zone",
    )
    # Manually setting service_key on the object after creation if needed
    # but the dataclass has init=False for service_key, so we might need to set it directly
    config = SubAccountConfig(
        name="test-subaccount",
        resource_group="default",
        service_key_json="path/to/key.json",
        model_to_deployment_urls={},
    )
    config.service_key = service_key
    return config


@patch("inspect_deployments.fetch_all_deployments")
@patch("inspect_deployments.MODEL_ALIASES", {"gpt-4": ["gpt-4-alias"]})
def test_inspect_subaccount(mock_fetch, mock_sub_config, capsys):
    # Setup mock deployments
    mock_fetch.return_value = [
        {
            "id": "dep-1",
            "url": "https://dep-1.com",
            "model_name": "gpt-4",
            "created_at": "2023-01-01",
        }
    ]

    # Run function
    inspect_subaccount("test-subaccount", mock_sub_config)

    # Capture output
    captured = capsys.readouterr()

    # Verify output contains key info
    assert "Subaccount: test-subaccount" in captured.out
    assert "dep-1" in captured.out
    assert "gpt-4" in captured.out
    assert "gpt-4-alias" in captured.out
    assert "https://dep-1.com" in captured.out

    # Verify fetch called correctly
    mock_fetch.assert_called_once_with(
        service_key=mock_sub_config.service_key,
        resource_group="default",
        force_refresh=True,
    )
