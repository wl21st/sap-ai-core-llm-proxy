"""
Unit tests for load_balancer.py module.

Tests cover:
- resolve_model_name function
- load_balance_url function
- reset_counters function
- Round-robin load balancing behavior
- Model fallback logic
"""

import pytest
from unittest.mock import MagicMock

from load_balancer import (
    resolve_model_name,
    load_balance_url,
    reset_counters,
    _load_balance_counters,
)
from config import ProxyConfig, SubAccountConfig


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def mock_proxy_config():
    """Create a mock ProxyConfig for testing."""
    config = MagicMock(spec=ProxyConfig)
    config.model_to_subaccounts = {}
    config.subaccounts = {}
    return config


@pytest.fixture
def sample_subaccount():
    """Create a sample SubAccountConfig for testing."""

    def _create(name, resource_group, urls_dict):
        subaccount = MagicMock(spec=SubAccountConfig)
        subaccount.name = name
        subaccount.resource_group = resource_group
        subaccount.model_to_deployment_urls = urls_dict
        return subaccount

    return _create


@pytest.fixture(autouse=True)
def reset_load_balance_counters():
    """Reset load balance counters before each test."""
    reset_counters()
    yield
    reset_counters()


# ============================================================================
# TEST resolve_model_name
# ============================================================================


class TestResolveModelName:
    """Tests for resolve_model_name function."""

    def test_exact_match_returns_model(self, mock_proxy_config):
        """Test that exact model matches are returned directly."""
        mock_proxy_config.model_to_subaccounts = {"gpt-4": ["account1"]}

        result = resolve_model_name("gpt-4", mock_proxy_config)

        assert result == "gpt-4"

    def test_claude_opus_fallback(self, mock_proxy_config):
        """Test Claude opus model fallback resolution."""
        mock_proxy_config.model_to_subaccounts = {
            "anthropic--claude-4.5-opus": ["account1"]
        }

        result = resolve_model_name("claude-opus", mock_proxy_config)

        assert result == "anthropic--claude-4.5-opus"

    def test_claude_haiku_fallback(self, mock_proxy_config):
        """Test Claude haiku model fallback resolution."""
        mock_proxy_config.model_to_subaccounts = {
            "anthropic--claude-4-haiku": ["account1"]
        }

        result = resolve_model_name("claude-haiku", mock_proxy_config)

        assert result == "anthropic--claude-4-haiku"

    def test_claude_sonnet_fallback(self, mock_proxy_config):
        """Test Claude sonnet model fallback resolution (default Claude)."""
        mock_proxy_config.model_to_subaccounts = {
            "anthropic--claude-4.5-sonnet": ["account1"]
        }

        result = resolve_model_name("claude-3", mock_proxy_config)

        assert result == "anthropic--claude-4.5-sonnet"

    def test_gemini_fallback(self, mock_proxy_config):
        """Test Gemini model fallback resolution."""
        mock_proxy_config.model_to_subaccounts = {"gemini-2.5-pro": ["account1"]}

        result = resolve_model_name("gemini-1.5-flash", mock_proxy_config)

        assert result == "gemini-2.5-pro"

    def test_other_model_no_fallback(self, mock_proxy_config):
        """Test that non-Claude/non-Gemini models fallback to DEFAULT_GPT_MODEL."""
        # DEFAULT_GPT_MODEL is "gpt-4.1" in load_balancer.py
        mock_proxy_config.model_to_subaccounts = {"gpt-4.1": ["account1"]}

        # gpt-3.5-turbo is not a Claude or Gemini model, so it goes through
        # the 'else' branch which tries DEFAULT_GPT_MODEL (gpt-4.1)
        result = resolve_model_name("gpt-3.5-turbo", mock_proxy_config)

        assert result == "gpt-4.1"

    def test_no_fallback_returns_none(self, mock_proxy_config):
        """Test that None is returned when no fallback exists."""
        mock_proxy_config.model_to_subaccounts = {}

        result = resolve_model_name("unknown-model", mock_proxy_config)

        assert result is None


# ============================================================================
# TEST load_balance_url
# ============================================================================


class TestLoadBalanceUrl:
    """Tests for load_balance_url function."""

    def test_single_subaccount_returns_url(
        self, mock_proxy_config, sample_subaccount
    ):
        """Test load balancing with a single subaccount."""
        subaccount = sample_subaccount(
            "account1", "default", {"gpt-4": ["https://url1.com"]}
        )
        mock_proxy_config.model_to_subaccounts = {"gpt-4": ["account1"]}
        mock_proxy_config.subaccounts = {"account1": subaccount}

        url, name, rg, model = load_balance_url("gpt-4", mock_proxy_config)

        assert url == "https://url1.com"
        assert name == "account1"
        assert rg == "default"
        assert model == "gpt-4"

    def test_round_robin_across_subaccounts(
        self, mock_proxy_config, sample_subaccount
    ):
        """Test round-robin load balancing across multiple subaccounts."""
        sub1 = sample_subaccount("account1", "rg1", {"gpt-4": ["https://url1.com"]})
        sub2 = sample_subaccount("account2", "rg2", {"gpt-4": ["https://url2.com"]})
        mock_proxy_config.model_to_subaccounts = {"gpt-4": ["account1", "account2"]}
        mock_proxy_config.subaccounts = {"account1": sub1, "account2": sub2}

        # First call should use account1
        _, name1, _, _ = load_balance_url("gpt-4", mock_proxy_config)
        assert name1 == "account1"

        # Second call should use account2
        _, name2, _, _ = load_balance_url("gpt-4", mock_proxy_config)
        assert name2 == "account2"

        # Third call should cycle back to account1
        _, name3, _, _ = load_balance_url("gpt-4", mock_proxy_config)
        assert name3 == "account1"

    def test_round_robin_within_subaccount_urls(
        self, mock_proxy_config, sample_subaccount
    ):
        """Test round-robin load balancing across multiple URLs in a subaccount."""
        subaccount = sample_subaccount(
            "account1",
            "default",
            {"gpt-4": ["https://url1.com", "https://url2.com", "https://url3.com"]},
        )
        mock_proxy_config.model_to_subaccounts = {"gpt-4": ["account1"]}
        mock_proxy_config.subaccounts = {"account1": subaccount}

        url1, _, _, _ = load_balance_url("gpt-4", mock_proxy_config)
        assert url1 == "https://url1.com"

        url2, _, _, _ = load_balance_url("gpt-4", mock_proxy_config)
        assert url2 == "https://url2.com"

        url3, _, _, _ = load_balance_url("gpt-4", mock_proxy_config)
        assert url3 == "https://url3.com"

        url4, _, _, _ = load_balance_url("gpt-4", mock_proxy_config)
        assert url4 == "https://url1.com"

    def test_model_not_found_raises_error(self, mock_proxy_config):
        """Test that ValueError is raised when model is not found."""
        mock_proxy_config.model_to_subaccounts = {}

        with pytest.raises(ValueError, match="not available in any subAccount"):
            load_balance_url("nonexistent-model", mock_proxy_config)

    def test_claude_model_fallback(self, mock_proxy_config, sample_subaccount):
        """Test Claude model fallback when requested model not found."""
        subaccount = sample_subaccount(
            "account1",
            "default",
            {"anthropic--claude-4.5-sonnet": ["https://url1.com"]},
        )
        mock_proxy_config.model_to_subaccounts = {
            "anthropic--claude-4.5-sonnet": ["account1"]
        }
        mock_proxy_config.subaccounts = {"account1": subaccount}

        url, name, _, model = load_balance_url("claude-3.5-sonnet", mock_proxy_config)

        assert model == "anthropic--claude-4.5-sonnet"
        assert url == "https://url1.com"

    def test_gemini_model_fallback(self, mock_proxy_config, sample_subaccount):
        """Test Gemini model fallback when requested model not found."""
        subaccount = sample_subaccount(
            "account1", "default", {"gemini-2.5-pro": ["https://url1.com"]}
        )
        mock_proxy_config.model_to_subaccounts = {"gemini-2.5-pro": ["account1"]}
        mock_proxy_config.subaccounts = {"account1": subaccount}

        url, name, _, model = load_balance_url("gemini-1.5-flash", mock_proxy_config)

        assert model == "gemini-2.5-pro"
        assert url == "https://url1.com"

    def test_no_urls_configured_raises_error(
        self, mock_proxy_config, sample_subaccount
    ):
        """Test that ValueError is raised when model has no URLs."""
        subaccount = sample_subaccount("account1", "default", {"gpt-4": []})
        mock_proxy_config.model_to_subaccounts = {"gpt-4": ["account1"]}
        mock_proxy_config.subaccounts = {"account1": subaccount}

        with pytest.raises(ValueError, match="No URLs for model"):
            load_balance_url("gpt-4", mock_proxy_config)


# ============================================================================
# TEST reset_counters
# ============================================================================


class TestResetCounters:
    """Tests for reset_counters function."""

    def test_reset_clears_counters(self, mock_proxy_config, sample_subaccount):
        """Test that reset_counters clears all load balancing counters."""
        subaccount = sample_subaccount(
            "account1", "default", {"gpt-4": ["https://url1.com", "https://url2.com"]}
        )
        mock_proxy_config.model_to_subaccounts = {"gpt-4": ["account1"]}
        mock_proxy_config.subaccounts = {"account1": subaccount}

        # Make some calls to increment counters
        load_balance_url("gpt-4", mock_proxy_config)
        load_balance_url("gpt-4", mock_proxy_config)

        # Reset counters
        reset_counters()

        # Next call should start from the first URL again
        url, _, _, _ = load_balance_url("gpt-4", mock_proxy_config)
        assert url == "https://url1.com"

    def test_reset_returns_empty_dict(self):
        """Test that counters are empty after reset."""
        reset_counters()
        assert _load_balance_counters == {}


# ============================================================================
# TEST edge cases
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_empty_subaccount_list_for_model(self, mock_proxy_config):
        """Test handling when model has empty subaccount list."""
        mock_proxy_config.model_to_subaccounts = {"gpt-4": []}

        with pytest.raises(ValueError, match="not available in any subAccount"):
            load_balance_url("gpt-4", mock_proxy_config)

    def test_missing_model_in_subaccount_urls(self, mock_proxy_config, sample_subaccount):
        """Test handling when subaccount doesn't have model's URLs."""
        # Create subaccount with a dict that returns empty list for the model
        subaccount = sample_subaccount("account1", "default", {})
        mock_proxy_config.model_to_subaccounts = {"gpt-4": ["account1"]}
        mock_proxy_config.subaccounts = {"account1": subaccount}

        with pytest.raises(ValueError, match="No URLs for model"):
            load_balance_url("gpt-4", mock_proxy_config)
