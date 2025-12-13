"""
Configuration loading utilities for SAP AI Core LLM Proxy.

This module handles loading and parsing configuration from JSON files.
"""

import json
from typing import Union, Dict, Any
from .models import ProxyConfig, SubAccountConfig


def load_config(file_path: str) -> Union[ProxyConfig, Dict[str, Any]]:
    """Load configuration from a JSON file with support for multiple subAccounts.
    
    Args:
        file_path: Path to the JSON configuration file
        
    Returns:
        ProxyConfig instance if new format with subAccounts, otherwise raw JSON dict
        
    Raises:
        FileNotFoundError: If the configuration file doesn't exist
        json.JSONDecodeError: If the file contains invalid JSON
    """
    with open(file_path, 'r') as file:
        config_json = json.load(file)
    
    # Check if this is the new format with subAccounts
    if 'subAccounts' in config_json:
        # Create a proper ProxyConfig instance
        proxy_conf = ProxyConfig(
            secret_authentication_tokens=config_json.get('secret_authentication_tokens', []),
            port=config_json.get('port', 3001),
            host=config_json.get('host', '127.0.0.1')
        )
        
        # Parse each subAccount
        for sub_name, sub_config in config_json.get('subAccounts', {}).items():
            proxy_conf.subaccounts[sub_name] = SubAccountConfig(
                name=sub_name,
                resource_group=sub_config.get('resource_group', 'default'),
                service_key_json=sub_config.get('service_key_json', ''),
                deployment_models=sub_config.get('deployment_models', {})
            )
        
        return proxy_conf
    else:
        # For backward compatibility - return the raw JSON
        return config_json