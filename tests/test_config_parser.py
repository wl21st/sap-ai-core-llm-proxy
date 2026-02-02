"""
Unit tests for config/config_parser.py module.

Tests model filtering logic including regex validation, filter precedence, and error handling.
"""

import pytest
import re
from unittest.mock import Mock, patch, mock_open
from config.config_parser import (
    validate_regex_patterns,
    apply_model_filters,
    ConfigValidationError,
)
from config.config_models import ModelFilters


class TestValidateRegexPatterns:
    """Tests for validate_regex_patterns function."""

    def test_valid_regex_patterns(self):
        """Test that valid regex patterns are compiled successfully."""
        patterns = ["^gpt-4.*", "claude-(opus|sonnet)-.*", ".*-test$"]
        compiled = validate_regex_patterns(patterns, "include")

        assert len(compiled) == 3
        assert all(isinstance(p, re.Pattern) for p in compiled)

    def test_invalid_regex_pattern_unclosed_bracket(self):
        """Test that invalid regex pattern (unclosed bracket) raises ConfigValidationError."""
        patterns = ["[unclosed"]

        with pytest.raises(ConfigValidationError) as exc_info:
            validate_regex_patterns(patterns, "exclude")

        assert "Invalid regex pattern in exclude filters" in str(exc_info.value)
        assert "[unclosed" in str(exc_info.value)

    def test_invalid_regex_pattern_invalid_group(self):
        """Test that invalid regex pattern (invalid group) raises ConfigValidationError."""
        patterns = ["(?P<invalid"]

        with pytest.raises(ConfigValidationError) as exc_info:
            validate_regex_patterns(patterns, "include")

        assert "Invalid regex pattern in include filters" in str(exc_info.value)
        assert "(?P<invalid" in str(exc_info.value)

    def test_empty_patterns_list(self):
        """Test that empty patterns list returns empty compiled list."""
        patterns = []
        compiled = validate_regex_patterns(patterns, "include")

        assert compiled == []

    def test_invalid_regex_backslash_escape(self):
        """Test that invalid regex pattern with bad escape sequence raises error."""
        patterns = [r"\k<invalid>"]

        with pytest.raises(ConfigValidationError) as exc_info:
            validate_regex_patterns(patterns, "include")

        assert "Invalid regex pattern in include filters" in str(exc_info.value)

    def test_invalid_regex_unbalanced_parentheses(self):
        """Test that unbalanced parentheses raises ConfigValidationError."""
        patterns = ["(unbalanced"]

        with pytest.raises(ConfigValidationError) as exc_info:
            validate_regex_patterns(patterns, "exclude")

        assert "Invalid regex pattern in exclude filters" in str(exc_info.value)
        assert "(unbalanced" in str(exc_info.value)

    def test_invalid_regex_lookahead_error(self):
        """Test that invalid lookahead pattern raises ConfigValidationError."""
        patterns = ["(?P<name>test)(?P=invalid)"]

        with pytest.raises(ConfigValidationError) as exc_info:
            validate_regex_patterns(patterns, "include")

        assert "Invalid regex pattern in include filters" in str(exc_info.value)


class TestApplyModelFilters:
    """Tests for apply_model_filters function."""

    def test_include_only_filtering(self):
        """Test include-only filtering keeps matching models, filters out non-matching."""
        models = {
            "gpt-4": ["url1"],
            "gpt-4-turbo": ["url2"],
            "claude-sonnet": ["url3"],
            "gemini-pro": ["url4"],
        }
        filters = ModelFilters(include=["^gpt-.*"], exclude=None)

        filtered_models, filtered_info = apply_model_filters(models, filters)

        assert "gpt-4" in filtered_models
        assert "gpt-4-turbo" in filtered_models
        assert "claude-sonnet" not in filtered_models
        assert "gemini-pro" not in filtered_models

        # Check filtered info
        filtered_names = [info[0] for info in filtered_info]
        assert "claude-sonnet" in filtered_names
        assert "gemini-pro" in filtered_names

    def test_exclude_only_filtering(self):
        """Test exclude-only filtering filters out matching models, keeps non-matching."""
        models = {
            "gpt-4": ["url1"],
            "gpt-4-test": ["url2"],
            "claude-sonnet": ["url3"],
            "gemini-1-pro": ["url4"],
            "gemini-2-pro": ["url5"],
        }
        filters = ModelFilters(include=None, exclude=[".*-test$", "^gemini-1.*"])

        filtered_models, filtered_info = apply_model_filters(models, filters)

        assert "gpt-4" in filtered_models
        assert "claude-sonnet" in filtered_models
        assert "gemini-2-pro" in filtered_models
        assert "gpt-4-test" not in filtered_models
        assert "gemini-1-pro" not in filtered_models

        # Check filtered info
        filtered_names = [info[0] for info in filtered_info]
        assert "gpt-4-test" in filtered_names
        assert "gemini-1-pro" in filtered_names

    def test_combined_include_exclude_filtering(self):
        """Test combined include+exclude filtering (include first, then exclude from included set)."""
        models = {
            "gpt-4": ["url1"],
            "gpt-4-preview": ["url2"],
            "gpt-4-turbo": ["url3"],
            "claude-sonnet": ["url4"],
        }
        filters = ModelFilters(include=["^gpt-.*"], exclude=[".*-preview$"])

        filtered_models, filtered_info = apply_model_filters(models, filters)

        # Should keep: gpt-4, gpt-4-turbo
        # Should filter: claude-sonnet (not in include), gpt-4-preview (in exclude)
        assert "gpt-4" in filtered_models
        assert "gpt-4-turbo" in filtered_models
        assert "gpt-4-preview" not in filtered_models
        assert "claude-sonnet" not in filtered_models

        # Check filtered info
        filtered_names = [info[0] for info in filtered_info]
        assert "gpt-4-preview" in filtered_names
        assert "claude-sonnet" in filtered_names

    def test_filter_precedence_exclude_after_include(self):
        """Test that filter precedence matches spec: include first, then exclude."""
        models = {
            "gpt-4": ["url1"],
            "gpt-4-preview": ["url2"],
            "claude-sonnet": ["url3"],
        }
        filters = ModelFilters(include=["^gpt-.*"], exclude=[".*-preview$"])

        filtered_models, filtered_info = apply_model_filters(models, filters)

        # Step 1: Include filters -> keeps gpt-4, gpt-4-preview (removes claude-sonnet)
        # Step 2: Exclude filters -> removes gpt-4-preview
        # Final: only gpt-4
        assert "gpt-4" in filtered_models
        assert "gpt-4-preview" not in filtered_models
        assert "claude-sonnet" not in filtered_models
        assert len(filtered_models) == 1

    def test_empty_missing_model_filters(self):
        """Test that empty/missing model_filters applies no filtering."""
        models = {
            "gpt-4": ["url1"],
            "claude-sonnet": ["url2"],
        }

        # Test with None filters
        filtered_models, filtered_info = apply_model_filters(models, None)
        assert filtered_models == models
        assert filtered_info == []

        # Test with empty include/exclude
        empty_filters = ModelFilters(include=None, exclude=None)
        filtered_models, filtered_info = apply_model_filters(models, empty_filters)
        assert filtered_models == models
        assert filtered_info == []

    def test_all_models_filtered_out(self):
        """Test behavior when all models are filtered out."""
        models = {
            "gpt-4-test": ["url1"],
            "claude-test": ["url2"],
            "gemini-test": ["url3"],
        }
        filters = ModelFilters(include=None, exclude=[".*-test$"])

        filtered_models, filtered_info = apply_model_filters(models, filters)

        assert len(filtered_models) == 0
        assert len(filtered_info) == 3

    def test_valid_pattern_matches_no_models(self):
        """Test that valid regex pattern that matches no models doesn't cause error."""
        models = {
            "gpt-4": ["url1"],
            "claude-sonnet": ["url2"],
        }
        filters = ModelFilters(include=["^llama-.*"], exclude=None)

        # Should not raise error, just filter out all models
        filtered_models, filtered_info = apply_model_filters(models, filters)

        assert len(filtered_models) == 0
        assert len(filtered_info) == 2

    def test_include_patterns_match_nothing(self):
        """Test behavior when include patterns match nothing (all models filtered out)."""
        models = {
            "gpt-4": ["url1"],
            "claude-sonnet": ["url2"],
        }
        filters = ModelFilters(include=["^nonexistent-.*"], exclude=None)

        filtered_models, filtered_info = apply_model_filters(models, filters)

        assert len(filtered_models) == 0
        assert len(filtered_info) == 2

    def test_empty_patterns_in_filters(self):
        """Test handling of empty pattern lists (not None, but empty [])."""
        models = {
            "gpt-4": ["url1"],
            "claude-sonnet": ["url2"],
        }
        filters = ModelFilters(include=[], exclude=[])

        filtered_models, filtered_info = apply_model_filters(models, filters)

        assert filtered_models == models
        assert filtered_info == []

    def test_unicode_model_names(self):
        """Test handling of unicode characters in model names."""
        models = {
            "gpt-4-日本語": ["url1"],
            "claude-sonnet-中文": ["url2"],
            "gemini-pro-한글": ["url3"],
        }
        filters = ModelFilters(include=[".*日本語$"], exclude=None)

        filtered_models, filtered_info = apply_model_filters(models, filters)

        assert "gpt-4-日本語" in filtered_models
        assert "claude-sonnet-中文" not in filtered_models
        assert "gemini-pro-한글" not in filtered_models

    def test_special_characters_in_model_names(self):
        """Test handling of special characters that need escaping in regex."""
        models = {
            "gpt-4.1": ["url1"],
            "claude-3.5-sonnet": ["url2"],
            "model+test": ["url3"],
        }
        # Using \. to match literal dot
        filters = ModelFilters(include=[r".*\.\d+.*"], exclude=None)

        filtered_models, filtered_info = apply_model_filters(models, filters)

        # Should match: gpt-4.1, claude-3.5-sonnet (contains .digit)
        assert "gpt-4.1" in filtered_models
        assert "claude-3.5-sonnet" in filtered_models
        assert "model+test" not in filtered_models

    def test_multiple_urls_per_model(self):
        """Test that filtering preserves multiple URLs per model."""
        models = {
            "gpt-4": ["url1", "url2", "url3"],
            "claude-sonnet": ["url4", "url5"],
        }
        filters = ModelFilters(include=["^gpt-.*"], exclude=None)

        filtered_models, filtered_info = apply_model_filters(models, filters)

        assert "gpt-4" in filtered_models
        assert len(filtered_models["gpt-4"]) == 3
        assert filtered_models["gpt-4"] == ["url1", "url2", "url3"]

    def test_case_sensitive_filtering(self):
        """Test that filtering is case-sensitive by default."""
        models = {
            "GPT-4": ["url1"],
            "gpt-4": ["url2"],
            "Claude-Sonnet": ["url3"],
        }
        filters = ModelFilters(include=["^gpt-.*"], exclude=None)

        filtered_models, filtered_info = apply_model_filters(models, filters)

        # Only lowercase gpt-4 should match
        assert "gpt-4" in filtered_models
        assert "GPT-4" not in filtered_models
        assert "Claude-Sonnet" not in filtered_models

    def test_empty_model_dict(self):
        """Test filtering with empty model dictionary."""
        models = {}
        filters = ModelFilters(include=["^gpt-.*"], exclude=[".*-test$"])

        filtered_models, filtered_info = apply_model_filters(models, filters)

        assert filtered_models == {}
        assert filtered_info == []
