"""
Version management for SAP AI Core LLM Proxy.

This module provides version and git hash information for the proxy server.
It works in multiple scenarios:
1. PyInstaller build: Reads from _version.txt bundled in the executable
2. Development mode: Reads from pyproject.toml and git
"""

import os
import subprocess
import sys


def get_version_info() -> tuple[str, str]:
    """Get version and git hash information.

    This function works in multiple scenarios:
    1. PyInstaller build: Reads from _version.txt bundled in the executable
    2. Development mode: Reads from pyproject.toml and git

    Returns:
        tuple: (version: str, git_hash: str)
    """
    # First, try to read from _version.txt (for PyInstaller builds)
    try:
        # Check if we're running in PyInstaller bundle
        if getattr(sys, "frozen", False):
            # Running in PyInstaller bundle
            bundle_dir = sys._MEIPASS
            version_file = os.path.join(bundle_dir, "_version.txt")
        else:
            # Running in normal Python
            version_file = "_version.txt"

        if os.path.exists(version_file):
            with open(version_file, "r") as f:
                lines = f.read().strip().split("\n")
                version = lines[0] if len(lines) > 0 else "unknown"
                git_hash = lines[1] if len(lines) > 1 else "unknown"
                return version, git_hash
    except Exception:
        pass

    # Fallback: Read from pyproject.toml and git (development mode)
    version = "unknown"
    git_hash = "unknown"

    # Try to get version from pyproject.toml
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError:
            tomllib = None

    if tomllib:
        try:
            with open("pyproject.toml", "rb") as f:
                data = tomllib.load(f)
                version = data.get("project", {}).get("version", "unknown")
        except Exception:
            pass

    # Try to get git hash
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        git_hash = result.stdout.strip()
    except Exception:
        pass

    return version, git_hash


def get_version() -> str:
    """Get version string.

    Returns:
        str: Version string or 'unknown' if not found
    """
    version, _ = get_version_info()
    return version


def get_git_hash() -> str:
    """Get current git commit hash (short version).

    Returns:
        str: Short git commit hash or 'unknown' if not available
    """
    _, git_hash = get_version_info()
    return git_hash


def get_version_string() -> str:
    """Get full version string with git hash.

    Returns:
        str: Version string in format 'version (git: hash)'
    """
    version, git_hash = get_version_info()
    return f"{version} (git: {git_hash})"
