#!/usr/bin/env python3
"""
Test script to verify Pydantic configuration models and loader.

This script demonstrates loading and using the Pydantic-based configuration
system with the provided config.json file.
"""

import json
from logging import Logger
import sys
from pathlib import Path

# Setup logging
from utils.logging_utils import get_client_logger

logger: Logger = get_client_logger(__name__)

# Import Pydantic models and loader
from config.pydantic_models import ProxyConfigModel
from config.pydantic_loader import (
    load_pydantic_config,
    config_to_json,
    validate_config_dict
)


def test_load_config():
    """Test loading configuration from config.json."""
    logger.info("=" * 60)
    logger.info("Test 1: Load config.json using Pydantic")
    logger.info("=" * 60)
    
    try:
        config = load_pydantic_config("config.json")
        
        logger.info(f"✓ Configuration loaded successfully")
        logger.info(f"  - Port: {config.port}")
        logger.info(f"  - Host: {config.host}")
        logger.info(f"  - Number of subaccounts: {len(config.subAccounts)}")
        logger.info(f"  - Authentication tokens: {len(config.secret_authentication_tokens)}")
        
        # Display subaccount information
        for subaccount_name, subaccount in config.subAccounts.items():
            logger.info(f"\n  Subaccount: {subaccount_name}")
            logger.info(f"    - Resource Group: {subaccount.resource_group}")
            logger.info(f"    - Service Key File: {subaccount.service_key_json}")
            logger.info(f"    - Deployment Models: {len(subaccount.deployment_models)}")
            for model_name, deployments in list(subaccount.deployment_models.items())[:3]:
                logger.info(f"      * {model_name}: {len(deployments)} deployment(s)")
        
        return config
        
    except Exception as e:
        logger.error(f"✗ Failed to load configuration: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_initialize_config(config):
    """Test initialization and model mapping."""
    logger.info("\n" + "=" * 60)
    logger.info("Test 2: Initialize config and build model mappings")
    logger.info("=" * 60)
    
    try:
        config.initialize()
        
        logger.info(f"✓ Configuration initialized successfully")
        logger.info(f"  - Global model mappings: {len(config.model_to_subaccounts)}")
        
        # Show sample model mappings
        for model_name, subaccounts in list(config.model_to_subaccounts.items())[:5]:
            logger.info(f"    * {model_name}: {subaccounts}")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Failed to initialize configuration: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_serialize_config(config):
    """Test serialization to JSON."""
    logger.info("\n" + "=" * 60)
    logger.info("Test 3: Serialize config to JSON")
    logger.info("=" * 60)
    
    try:
        output_file = "config_serialized.json"
        config_to_json(config, output_file)
        
        logger.info(f"✓ Configuration serialized to {output_file}")
        
        # Verify the file was created
        if Path(output_file).exists():
            file_size = Path(output_file).stat().st_size
            logger.info(f"  - File size: {file_size} bytes")
            
            # Try to load it back
            with open(output_file, 'r') as f:
                reloaded = json.load(f)
            logger.info(f"  - Successfully reloaded from file")
            
        return True
        
    except Exception as e:
        logger.error(f"✗ Failed to serialize configuration: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_validation():
    """Test configuration validation."""
    logger.info("\n" + "=" * 60)
    logger.info("Test 4: Validate configuration")
    logger.info("=" * 60)
    
    try:
        # Load original config for validation
        with open("config.json", 'r') as f:
            config_dict = json.load(f)
        
        from config.pydantic_loader import validate_config_dict
        
        result = validate_config_dict(config_dict)
        logger.info(f"✓ Configuration validation passed: {result}")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Configuration validation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_invalid_config():
    """Test validation with invalid configuration."""
    logger.info("\n" + "=" * 60)
    logger.info("Test 5: Test validation with invalid configuration")
    logger.info("=" * 60)
    
    try:
        # Create invalid config (missing required field)
        invalid_config = {
            "subAccounts": {
                "testAccount": {
                    "resource_group": "default",
                    # Missing "service_key_json" (required)
                    "deployment_models": {}
                }
            }
        }
        
        from config.pydantic_loader import validate_config_dict
        validate_config_dict(invalid_config)
        logger.warning("✗ Invalid configuration was accepted (unexpected)")
        return False
        
    except ValueError as e:
        logger.info(f"✓ Invalid configuration correctly rejected")
        logger.info(f"  - Error: {str(e)[:100]}...")
        return True
    except Exception as e:
        logger.error(f"✗ Unexpected error: {e}")
        return False


def test_port_validation():
    """Test port range validation."""
    logger.info("\n" + "=" * 60)
    logger.info("Test 6: Test port range validation")
    logger.info("=" * 60)
    
    try:
        # Try to create config with invalid port
        invalid_config = {
            "subAccounts": {},
            "port": 99999,  # Invalid port (> 65535)
            "host": "127.0.0.1"
        }
        
        from config.pydantic_loader import validate_config_dict
        validate_config_dict(invalid_config)
        logger.warning("✗ Invalid port was accepted (unexpected)")
        return False
        
    except ValueError as e:
        logger.info(f"✓ Invalid port correctly rejected")
        logger.info(f"  - Error: {str(e)[:100]}...")
        return True
    except Exception as e:
        logger.error(f"✗ Unexpected error: {e}")
        return False


def main():
    """Run all tests."""
    logger.info("\n" + "=" * 60)
    logger.info("Pydantic Configuration System Test Suite")
    logger.info("=" * 60)
    
    results = {}
    
    # Test 1: Load config
    config = test_load_config()
    results['Load Config'] = config is not None
    
    if config:
        # Test 2: Initialize
        results['Initialize Config'] = test_initialize_config(config)
        
        # Test 3: Serialize
        results['Serialize Config'] = test_serialize_config(config)
    
    # Test 4: Validation
    results['Validation'] = test_validation()
    
    # Test 5: Invalid config
    results['Invalid Config Detection'] = test_invalid_config()
    
    # Test 6: Port validation
    results['Port Range Validation'] = test_port_validation()
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("Test Summary")
    logger.info("=" * 60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, passed_test in results.items():
        status = "✓ PASS" if passed_test else "✗ FAIL"
        logger.info(f"{status}: {test_name}")
    
    logger.info(f"\nTotal: {passed}/{total} tests passed")
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
