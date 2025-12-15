"""
Logging configuration for SAP AI Core LLM Proxy.

This module sets up the main application logger and a specialized token usage logger.
"""

import logging
import os


def setup_logging(debug: bool = False) -> None:
    """Configure the main application logging.
    
    Args:
        debug: If True, set logging level to DEBUG, otherwise INFO
    """
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    if debug:
        logging.debug("Debug mode enabled")


def get_token_logger() -> logging.Logger:
    """Get or create the token usage logger.
    
    This logger writes token usage information to a separate log file
    for tracking and billing purposes.
    
    Returns:
        Configured Logger instance for token usage
    """
    # Create a new logger for token usage
    token_logger = logging.getLogger('token_usage')
    
    # Only configure if not already configured
    if not token_logger.handlers:
        token_logger.setLevel(logging.INFO)
        
        # Create a file handler for token usage logging
        log_directory = 'logs'
        if not os.path.exists(log_directory):
            os.makedirs(log_directory)
        log_file = os.path.join(log_directory, 'token_usage.log')
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        
        # Create a formatter for token usage logging
        formatter = logging.Formatter('%(asctime)s - %(message)s')
        file_handler.setFormatter(formatter)
        
        # Add the file handler to the token usage logger
        token_logger.addHandler(file_handler)
    
    return token_logger