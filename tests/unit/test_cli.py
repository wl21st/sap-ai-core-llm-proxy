"""
Unit tests for cli.py - Command-line argument parsing.

Tests CLI argument parsing functions.
"""

import sys
import pytest

from cli import parse_arguments


class TestCLIArguments:
    """Tests for CLI argument parsing."""

    def test_default_values(self, monkeypatch):
        """Test that default values are set correctly."""
        # Simulate no command line arguments
        monkeypatch.setattr(sys, 'argv', ['proxy_server.py'])
        args = parse_arguments()
        
        assert args.config == "config.json"
        assert args.debug is False
        assert args.port is None

    def test_custom_config_path(self, monkeypatch):
        """Test custom config file path."""
        monkeypatch.setattr(sys, 'argv', ['proxy_server.py', '--config', 'custom_config.json'])
        args = parse_arguments()
        
        assert args.config == "custom_config.json"

    def test_custom_config_short_flag(self, monkeypatch):
        """Test custom config with short flag."""
        monkeypatch.setattr(sys, 'argv', ['proxy_server.py', '-c', 'test.json'])
        args = parse_arguments()
        
        assert args.config == "test.json"

    def test_debug_flag(self, monkeypatch):
        """Test debug flag is set correctly."""
        monkeypatch.setattr(sys, 'argv', ['proxy_server.py', '--debug'])
        args = parse_arguments()
        
        assert args.debug is True

    def test_debug_short_flag(self, monkeypatch):
        """Test debug with short flag."""
        monkeypatch.setattr(sys, 'argv', ['proxy_server.py', '-d'])
        args = parse_arguments()
        
        assert args.debug is True

    def test_port_argument(self, monkeypatch):
        """Test custom port argument."""
        monkeypatch.setattr(sys, 'argv', ['proxy_server.py', '--port', '8080'])
        args = parse_arguments()
        
        assert args.port == 8080

    def test_port_short_flag(self, monkeypatch):
        """Test port with short flag."""
        monkeypatch.setattr(sys, 'argv', ['proxy_server.py', '-p', '9000'])
        args = parse_arguments()
        
        assert args.port == 9000

    def test_combined_arguments(self, monkeypatch):
        """Test multiple arguments together."""
        monkeypatch.setattr(sys, 'argv', [
            'proxy_server.py',
            '-c', 'my_config.json',
            '-d',
            '-p', '5000'
        ])
        args = parse_arguments()
        
        assert args.config == "my_config.json"
        assert args.debug is True
        assert args.port == 5000

    def test_port_requires_integer(self, monkeypatch):
        """Test that port requires an integer value."""
        monkeypatch.setattr(sys, 'argv', ['proxy_server.py', '--port', 'not_a_number'])
        
        with pytest.raises(SystemExit):
            parse_arguments()
