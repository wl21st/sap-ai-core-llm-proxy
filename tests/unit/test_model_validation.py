import pytest
from proxy_helpers import Detector


class TestModelValidation:
    """Tests for Detector.validate_model_mapping."""

    def test_valid_mappings(self):
        """Test cases that should pass validation."""
        valid_cases = [
            ("gpt-4", "gpt-4"),
            (
                "gpt-4",
                "gpt-4-0613",
            ),  # Prefix match logic (or partial) - checking current impl
            ("gpt-4-32k", "gpt-4"),
            ("claude-3-sonnet", "anthropic.claude-3-sonnet-20240229-v1:0"),
            ("gemini-1.5-pro", "gemini-1.5-pro-001"),
            ("text-embedding-3-small", "text-embedding-3-small"),
        ]
        for configured, backend in valid_cases:
            is_valid, reason = Detector.validate_model_mapping(configured, backend)
            assert is_valid, (
                f"Expected valid for {configured} -> {backend}, got error: {reason}"
            )
            assert reason is None

    def test_family_mismatch(self):
        """Test mismatching model families."""
        invalid_cases = [
            ("gpt-4", "claude-3-opus"),
            ("claude-3-sonnet", "gemini-1.5-pro"),
            ("gemini-pro", "gpt-3.5-turbo"),
            ("text-embedding-3", "gpt-4"),
        ]
        for configured, backend in invalid_cases:
            is_valid, reason = Detector.validate_model_mapping(configured, backend)
            assert not is_valid, f"Expected invalid for {configured} -> {backend}"
            assert "Family mismatch" in reason

    def test_version_mismatch(self):
        """Test mismatching model versions."""
        invalid_cases = [
            ("gpt-4", "gpt-3.5-turbo"),
            ("claude-3-5-sonnet", "claude-3-sonnet"),
            ("gemini-1.5-pro", "gemini-1.0-pro"),
        ]
        for configured, backend in invalid_cases:
            is_valid, reason = Detector.validate_model_mapping(configured, backend)
            assert not is_valid, f"Expected invalid for {configured} -> {backend}"
            assert "Version mismatch" in reason

    def test_variant_mismatch(self):
        """Test mismatching model variants."""
        invalid_cases = [
            ("claude-3-sonnet", "claude-3-haiku"),
            ("claude-3-opus", "claude-3-sonnet"),
            ("gemini-1.5-pro", "gemini-1.5-flash"),
            ("gpt-4-turbo", "gpt-4-omni"),  # Assumes 'omni' is in variants list
        ]
        for configured, backend in invalid_cases:
            is_valid, reason = Detector.validate_model_mapping(configured, backend)
            assert not is_valid, f"Expected invalid for {configured} -> {backend}"
            assert "Variant mismatch" in reason

    def test_edge_cases(self):
        """Test edge cases like missing inputs."""
        assert Detector.validate_model_mapping(None, "gpt-4") == (True, None)
        assert Detector.validate_model_mapping("gpt-4", None) == (True, None)
        assert Detector.validate_model_mapping("", "") == (True, None)

    def test_case_insensitivity(self):
        """Test that validation is case insensitive."""
        is_valid, _ = Detector.validate_model_mapping("GPT-4", "gpt-4")
        assert is_valid

        is_valid, reason = Detector.validate_model_mapping("GPT-4", "GEMINI-PRO")
        assert not is_valid
        assert "Family mismatch" in reason
