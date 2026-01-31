"""
Command-line argument parsing for SAP AI Core LLM Proxy.

This module handles CLI argument parsing for the proxy server.
"""

import argparse

from version import get_version_string


def parse_arguments():
    """Parse command-line arguments for the proxy server.
    
    Returns:
        argparse.Namespace: Parsed command-line arguments with the following attributes:
            - config (str): Path to configuration file (default: "config.json")
            - debug (bool): Enable debug mode
            - port (int | None): Port number to run the server on
    """
    version_string = get_version_string()
    parser = argparse.ArgumentParser(
        description=f"Proxy server for AI models - {version_string}",
        epilog=f"Version: {version_string}",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {version_string}",
        help="Show version information and exit",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default="config.json",
        help="Path to the configuration file",
    )
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug mode")
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=None,
        help="Port number to run the server on (overrides config file)",
    )
    return parser.parse_args()
