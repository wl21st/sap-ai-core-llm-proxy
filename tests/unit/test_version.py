"""
Unit tests for version.py - Version management utilities.

Tests version information retrieval functions.
"""

import pytest

from version import get_version, get_git_hash, get_version_info, get_version_string


class TestVersionInfo:
    """Tests for version information functions."""

    def test_get_version_returns_string(self):
        """Test that get_version returns a string."""
        version = get_version()
        assert isinstance(version, str)
        assert len(version) > 0

    def test_get_git_hash_returns_string(self):
        """Test that get_git_hash returns a string."""
        git_hash = get_git_hash()
        assert isinstance(git_hash, str)
        assert len(git_hash) > 0

    def test_get_version_info_returns_tuple(self):
        """Test that get_version_info returns a tuple of two strings."""
        result = get_version_info()
        assert isinstance(result, tuple)
        assert len(result) == 2
        version, git_hash = result
        assert isinstance(version, str)
        assert isinstance(git_hash, str)

    def test_get_version_string_format(self):
        """Test that get_version_string returns correct format."""
        version_string = get_version_string()
        assert isinstance(version_string, str)
        # Should contain version and git hash in format "version (git: hash)"
        assert "(git:" in version_string
        assert ")" in version_string

    def test_get_version_matches_version_info(self):
        """Test that get_version matches first element of get_version_info."""
        version = get_version()
        version_info = get_version_info()
        assert version == version_info[0]

    def test_get_git_hash_matches_version_info(self):
        """Test that get_git_hash matches second element of get_version_info."""
        git_hash = get_git_hash()
        version_info = get_version_info()
        assert git_hash == version_info[1]

    def test_version_string_contains_version_and_hash(self):
        """Test that version string contains both version and hash."""
        version = get_version()
        git_hash = get_git_hash()
        version_string = get_version_string()
        
        assert version in version_string
        assert git_hash in version_string

    def test_version_not_unknown_in_dev_mode(self):
        """Test that version is not 'unknown' when pyproject.toml exists."""
        version = get_version()
        # In development mode with pyproject.toml present, version should be found
        # Allow 'unknown' only if pyproject.toml is missing
        import os
        if os.path.exists("pyproject.toml"):
            assert version != "unknown", "Version should be read from pyproject.toml"

    def test_git_hash_not_unknown_in_repo(self):
        """Test that git hash is not 'unknown' when in a git repo."""
        git_hash = get_git_hash()
        # In a git repository, git hash should be found
        import os
        if os.path.exists(".git"):
            assert git_hash != "unknown", "Git hash should be available in git repo"
            # Git short hash is typically 7-10 characters
            assert len(git_hash) >= 7, "Git hash should be at least 7 characters"
