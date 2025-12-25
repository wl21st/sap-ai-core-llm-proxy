"""
Logging configuration for SAP AI Core LLM Proxy.

This module sets up a hierarchical logging structure with specialized loggers:
- app (parent logger with console output)
- app.server (server-related logs → server_YYYYMMDD_hhmmss.log)
- app.transport (transport/network logs → transport_YYYYMMDD_hhmmss.log)
- app.token_usage (token usage tracking → token_usage_YYYYMMDD_hhmmss.log)
"""

import logging
import os
import threading
from datetime import datetime

DEFAULT_LOG_FOLDER = 'logs'

# Module-level flag to ensure setup_logging() is called only once
_setup_lock = threading.Lock()
_loggers_initialized = False


def init_logging(debug: bool = True) -> None:
    """Configure the main application logging.
    
    This function is idempotent and will only configure logging on the first call.
    Subsequent calls will be ignored to prevent reconfiguring the logging system.

    Args:
        debug: If True, set logging level to DEBUG, otherwise INFO
    """
    global _loggers_initialized

    with _setup_lock:
        if _loggers_initialized:
            return

        level = logging.DEBUG if debug else logging.INFO

        # Configure basic logging for console output
        logging.basicConfig(
            level=level,
            format='%(asctime)s.%(msecs)03d - [%(threadName)s] - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # Create log directory and archive directory if they don't exist
        if not os.path.exists(DEFAULT_LOG_FOLDER):
            os.makedirs(DEFAULT_LOG_FOLDER)

        archive_folder = os.path.join(DEFAULT_LOG_FOLDER, 'archive')
        if not os.path.exists(archive_folder):
            os.makedirs(archive_folder)

        # Generate timestamp for log files (YYYYMMDD_hhmmss format)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Set up parent logger
        parent_logger = logging.getLogger('app')
        parent_logger.setLevel(level)

        # Set up specialized child loggers with timestamped file handlers
        _setup_child_logger('app.server', f'server_{timestamp}.log', level)
        _setup_child_logger('app.transport', f'transport_{timestamp}.log', level)
        _setup_child_logger('app.client', f'client_{timestamp}.log', level)

        _loggers_initialized = True

        if debug:
            logging.debug(f"Hierarchical logging system initialized with timestamp: {timestamp}")


def _setup_child_logger(logger_name: str, log_file: str, level: int) -> None:
    """Set up a child logger with its own file handler.
    
    Args:
        logger_name: Name of the logger (e.g., 'app.server')
        log_file: Name of the log file (e.g., 'server.log')
        level: Logging level for this logger
    """
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)

    # Create file handler
    log_path = os.path.join(DEFAULT_LOG_FOLDER, log_file)
    file_handler = logging.FileHandler(log_path)
    file_handler.setLevel(level)

    # Set formatter for file handler
    formatter = logging.Formatter(
        '%(asctime)s.%(msecs)03d - [%(threadName)s] - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)

    # Add handler to logger
    logger.addHandler(file_handler)

    # Ensure propagation to parent (for console output)
    logger.propagate = True


def get_default_server_logger() -> logging.Logger:
    """Get the server logger for Flask routes and request handling.

    Returns:
        Logger instance that writes to logs/server_YYYYMMDD_hhmmss.log
    """
    return logging.getLogger('app.server')


def get_server_logger(name: str) -> logging.Logger:
    """Get the server logger for Flask routes and request handling.

    Returns:
        Logger instance that writes to logs/server_YYYYMMDD_hhmmss.log
    """
    return logging.getLogger('app.server.' + name)


def get_default_transport_logger() -> logging.Logger:
    """Get the transport logger for network/SDK communication.

    Returns:
        Logger instance that writes to logs/transport_YYYYMMDD_hhmmss.log
    """
    return logging.getLogger('app.transport')


def get_transport_logger(name: str) -> logging.Logger:
    """Get the transport logger for network/SDK communication.

    Returns:
        Logger instance that writes to logs/transport_YYYYMMDD_hhmmss.log
    """
    return logging.getLogger('app.transport.' + name)


def get_default_client_logger() -> logging.Logger:
    """Get the transport logger for network/SDK communication.

    Returns:
        Logger instance that writes to logs/transport_YYYYMMDD_hhmmss.log
    """
    return logging.getLogger('app.client')


def get_client_logger(name: str) -> logging.Logger:
    """Get the transport logger for network/SDK communication.

    Returns:
        Logger instance that writes to logs/transport_YYYYMMDD_hhmmss.log
    """
    return logging.getLogger('app.client.' + name)


# Initialize logging when module is imported
init_logging()
