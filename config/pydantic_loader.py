"""
Configuration loading utilities using Pydantic models for SAP AI Core LLM Proxy.

This module handles loading and parsing configuration from JSON files
using Pydantic v2 for validation and serialization.
"""

import json
import logging
from pathlib import Path
from typing import Union, Dict, Any

from .pydantic_models import ProxyConfigModel, ServiceKeyModel


logger = logging.getLogger(__name__)


def load_pydantic_config(file_path: str) -> ProxyConfigModel:
    """Load configuration from a JSON file using Pydantic models.
    
    This function reads a JSON configuration file and parses it into a
    validated ProxyConfigModel instance. The file should follow the structure:
    
    {
        "subAccounts": {
            "subAccountName": {
                "resource_group": "default",
                "service_key_json": "path/to/key.json",
                "deployment_models": {
                    "model-name": ["deployment-url", ...]
                }
            }
        },
        "secret_authentication_tokens": ["token1", "token2"],
        "port": 3001,
        "host": "127.0.0.1"
    }
    
    Args:
        file_path: Path to the JSON configuration file
        
    Returns:
        ProxyConfigModel instance with validated configuration
        
    Raises:
        FileNotFoundError: If the configuration file doesn't exist
        json.JSONDecodeError: If the file contains invalid JSON
        ValueError: If the configuration fails Pydantic validation
    """
    try:
        # Check if file exists
        config_path = Path(file_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")
        
        # Read and parse JSON
        logger.debug(f"Loading configuration from: {file_path}")
        with open(file_path, 'r') as file:
            config_json = json.load(file)
        
        # Validate and parse using Pydantic
        config = ProxyConfigModel(**config_json)
        logger.info(f"Successfully loaded configuration with {len(config.subAccounts)} subaccounts")
        
        return config
        
    except FileNotFoundError as e:
        logger.error(f"Configuration file not found: {file_path}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in configuration file: {e}")
        raise ValueError(f"Invalid JSON in {file_path}: {e}")
    except ValueError as e:
        logger.error(f"Configuration validation failed: {e}")
        raise


def load_pydantic_config_with_service_keys(
    config_file_path: str,
    service_keys_dir: str = "."
) -> ProxyConfigModel:
    """Load configuration and resolve service key files.
    
    This function loads the main configuration and then loads service key
    JSON files referenced in each subaccount configuration.
    
    Args:
        config_file_path: Path to the main configuration JSON file
        service_keys_dir: Directory where service key JSON files are located
        
    Returns:
        ProxyConfigModel instance with service keys loaded
        
    Raises:
        FileNotFoundError: If configuration or service key files don't exist
        json.JSONDecodeError: If JSON files are invalid
        ValueError: If configuration or service key validation fails
    """
    # Load main configuration
    config = load_pydantic_config(config_file_path)
    
    # Load service keys for each subaccount
    for subaccount_name, subaccount in config.subAccounts.items():
        if subaccount.service_key_json:
            try:
                key_file_path = Path(service_keys_dir) / subaccount.service_key_json
                logger.debug(f"Loading service key for {subaccount_name}: {key_file_path}")
                
                with open(key_file_path, 'r') as f:
                    key_data = json.load(f)
                
                # Validate and set service key
                subaccount.service_key = ServiceKeyModel(**key_data)
                logger.info(f"Loaded service key for subaccount: {subaccount_name}")
                
            except FileNotFoundError as e:
                logger.error(f"Service key file not found for {subaccount_name}: {key_file_path}")
                raise FileNotFoundError(
                    f"Service key file not found: {key_file_path}"
                )
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in service key file: {key_file_path}")
                raise ValueError(
                    f"Invalid JSON in service key file {key_file_path}: {e}"
                )
            except ValueError as e:
                logger.error(f"Service key validation failed for {subaccount_name}: {e}")
                raise ValueError(
                    f"Invalid service key for {subaccount_name}: {e}"
                )
    
    # Initialize configuration (build model mappings)
    config.initialize()
    logger.info("Configuration initialized successfully")
    
    return config


def config_to_json(config: ProxyConfigModel, file_path: str) -> None:
    """Save ProxyConfigModel to a JSON file.
    
    This function serializes a ProxyConfigModel instance to JSON format.
    Note: Service keys and runtime fields are excluded from serialization.
    
    Args:
        config: The ProxyConfigModel instance to save
        file_path: Path where the JSON file should be written
        
    Raises:
        IOError: If the file cannot be written
    """
    try:
        logger.debug(f"Saving configuration to: {file_path}")
        config_dict = config.model_dump(
            exclude={'model_to_subaccounts', 'service_key', 'normalized_models', 'token_info'},
            exclude_none=False
        )
        
        with open(file_path, 'w') as f:
            json.dump(config_dict, f, indent=2)
        
        logger.info(f"Configuration saved to: {file_path}")
        
    except IOError as e:
        logger.error(f"Failed to write configuration file: {e}")
        raise


def validate_config_dict(config_dict: Dict[str, Any]) -> bool:
    """Validate a configuration dictionary without creating a model instance.
    
    This function performs lightweight validation of a config dictionary
    without fully instantiating the ProxyConfigModel.
    
    Args:
        config_dict: Dictionary to validate
        
    Returns:
        True if validation succeeds
        
    Raises:
        ValueError: If validation fails
    """
    try:
        ProxyConfigModel(**config_dict)
        return True
    except ValueError as e:
        logger.error(f"Configuration validation failed: {e}")
        raise
