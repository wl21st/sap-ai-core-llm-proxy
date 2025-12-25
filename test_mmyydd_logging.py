#!/usr/bin/env python3
"""
Test script for the MMYYDD_hhmmss timestamped hierarchical logging structure.
"""

from utils.logging_utils import get_server_logger, get_transport_logger, get_token_usage_logger
import logging
import os

def test_mmyydd_logging():
    """Test the MMYYDD_hhmmss timestamped hierarchical logging structure."""
    print("Testing MMYYDD_hhmmss timestamped hierarchical logging structure...")
    
    # Get the specialized loggers
    server_logger = get_server_logger()
    transport_logger = get_transport_logger()
    token_logger = get_token_usage_logger()
    
    # Test server logger
    server_logger.info("Server started on port 5000")
    server_logger.warning("High memory usage detected")
    server_logger.error("Failed to process request")
    
    # Test transport logger
    transport_logger.info("Connecting to SAP AI Core")
    transport_logger.debug("HTTP request: POST /v2/inference/deployments")
    transport_logger.warning("Retry attempt 2/3")
    
    # Test token usage logger
    token_logger.info("Token usage: 150 input, 75 output")
    token_logger.info("Cost calculation: $0.0045")
    
    # Test parent logger (should appear in console only)
    parent_logger = logging.getLogger('app')
    parent_logger.info("Application initialized successfully")
    
    print("\nLogging test completed!")
    print("\nCurrent log files (should use MMYYDD_hhmmss format):")
    
    # List current log files
    logs_dir = 'logs'
    if os.path.exists(logs_dir):
        log_files = [f for f in os.listdir(logs_dir) if f.endswith('.log')]
        for log_file in sorted(log_files):
            print(f"- logs/{log_file}")
    
    print("\nArchived log files:")
    archive_dir = 'logs/archive'
    if os.path.exists(archive_dir):
        archive_files = [f for f in os.listdir(archive_dir) if f.endswith('.log')]
        print(f"- {len(archive_files)} files in logs/archive/")
    
    print("\nAll messages should also appear in console output above.")
    print("New log files should follow format: [type]_MMYYDD_hhmmss.log")

if __name__ == "__main__":
    test_mmyydd_logging()
