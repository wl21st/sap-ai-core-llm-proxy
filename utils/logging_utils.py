"""
Logging configuration for SAP AI Core LLM Proxy.

This module sets up a hierarchical logging structure with specialized loggers:
- app (parent logger with console output)
- app.server (server-related logs → server_YYYYMMDD_hhmmss.log)
- app.transport (transport/network logs → transport_YYYYMMDD_hhmmss.log)
- app.client (client-related logs → client_YYYYMMDD_hhmmss.log)

Child loggers are initialized lazily on first access to avoid creating empty log files.
"""

import gzip
import logging
import os
import shutil
import threading
from datetime import datetime, timedelta

DEFAULT_LOG_FOLDER = "logs"
ARCHIVE_AGE_HOURS = 24  # 1 day in hours

# Module-level flags for logging initialization and lazy child logger setup
_setup_lock = threading.Lock()
_loggers_initialized = False
_child_loggers_setup = set()
_log_timestamp = None


def _gzip_file(src_path: str, dst_path: str) -> None:
    """Gzip a file and remove the original (GNU gzip behavior)."""
    with open(src_path, "rb") as f_in:
        with gzip.open(dst_path, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
    os.remove(src_path)


def init_logging(debug: bool = True) -> None:
    """Configure the main application logging.

    This function is idempotent and will only configure logging on the first call.
    Subsequent calls will be ignored to prevent reconfiguring the logging system.

    Child loggers (app.server, app.transport, app.client) are initialized lazily
    on first access to avoid creating empty log files.

    Args:
        debug: If True, set logging level to DEBUG, otherwise INFO
    """
    global _loggers_initialized, _log_timestamp

    with _setup_lock:
        if _loggers_initialized:
            return

        level = logging.DEBUG if debug else logging.INFO

        # Configure basic logging for console output
        logging.basicConfig(
            level=level,
            format="%(asctime)s.%(msecs)03d [%(levelname)s] [%(threadName)s] [%(filename)s:%(lineno)d]:  %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # Create log directory and archive directory if they don't exist
        if not os.path.exists(DEFAULT_LOG_FOLDER):
            os.makedirs(DEFAULT_LOG_FOLDER)

        archive_folder = os.path.join(DEFAULT_LOG_FOLDER, "archive")
        if not os.path.exists(archive_folder):
            os.makedirs(archive_folder)

        # Move existing log files to archive folder, gzip only if older than ARCHIVE_AGE_HOURS
        existing_logs = [
            f for f in os.listdir(DEFAULT_LOG_FOLDER) if f.endswith(".log")
        ]
        for log_file in existing_logs:
            src = os.path.join(DEFAULT_LOG_FOLDER, log_file)
            mtime = os.path.getmtime(src)
            file_age = datetime.now() - datetime.fromtimestamp(mtime)
            if file_age > timedelta(hours=ARCHIVE_AGE_HOURS):
                dst = os.path.join(archive_folder, log_file + ".gz")
                _gzip_file(src, dst)
                logging.info(f"Gzipped moved log file {log_file} to {dst}")
            else:
                dst = os.path.join(archive_folder, log_file)
                shutil.move(src, dst)
                logging.info(f"Moved log file {log_file} to {dst} without gzipping")

        # Gzip any existing log files in archive that are older than ARCHIVE_AGE_DAYS days
        archive_logs = [f for f in os.listdir(archive_folder) if f.endswith(".log")]
        for log_file in archive_logs:
            src = os.path.join(archive_folder, log_file)
            mtime = os.path.getmtime(src)
            file_age = datetime.now() - datetime.fromtimestamp(mtime)
            if file_age > timedelta(hours=ARCHIVE_AGE_HOURS):
                dst = os.path.join(archive_folder, log_file + ".gz")
                _gzip_file(src, dst)
                logging.info(
                    f"Gzipped old log file {log_file} in archive (age: {file_age.days} days) to {dst}"
                )

        # Generate timestamp for log files (YYYY-MM-DD_HH-MM-SS format)
        # Store it globally for lazy child logger initialization
        _log_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        # Set up parent logger
        parent_logger = logging.getLogger("app")
        parent_logger.setLevel(level)

        # Child loggers (server, transport, client) will be initialized lazily
        # when first accessed to avoid creating empty log files

        _loggers_initialized = True

        if debug:
            logging.debug(
                f"Hierarchical logging system initialized with timestamp: {_log_timestamp}"
            )


def _ensure_child_logger_initialized(logger_base_name: str) -> None:
    """Lazily initialize a child logger on first access.

    This function ensures that child loggers are only set up when they're actually
    used, preventing the creation of empty log files.

    Args:
        logger_base_name: Base name without 'app.' prefix (e.g., 'server', 'transport', 'client')
    """
    logger_name = f"app.{logger_base_name}"

    # Quick check without lock for performance
    if logger_name in _child_loggers_setup:
        return

    with _setup_lock:
        # Double-check after acquiring lock
        if logger_name in _child_loggers_setup:
            return

        if _log_timestamp is None:
            raise RuntimeError("Logging not initialized. Call init_logging() first.")

        log_file = f"{logger_base_name}_{_log_timestamp}.log"
        level = logging.getLogger("app").level
        _setup_child_logger(logger_name, log_file, level)
        _child_loggers_setup.add(logger_name)


def _setup_child_logger(logger_name: str, log_file: str, level: int) -> None:
    """Set up a child logger with its own file handler.

    Args:
        logger_name: Name of the logger (e.g., 'app.server')
        log_file: Name of the log file (e.g., 'server_20231225_120000.log')
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
        fmt="%(asctime)s.%(msecs)03d [%(levelname)s] [%(threadName)s] [%(filename)s:%(lineno)d]:  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
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
    _ensure_child_logger_initialized("server")
    return logging.getLogger("app.server")


def get_server_logger(name: str) -> logging.Logger:
    """Get the server logger for Flask routes and request handling.

    Args:
        name: Name suffix for the logger (e.g., 'routes' -> 'app.server.routes')

    Returns:
        Logger instance that writes to logs/server_YYYYMMDD_hhmmss.log
    """
    _ensure_child_logger_initialized("server")
    return logging.getLogger("app.server." + name)


def get_default_transport_logger() -> logging.Logger:
    """Get the transport logger for network/SDK communication.

    Returns:
        Logger instance that writes to logs/transport_YYYYMMDD_hhmmss.log
    """
    _ensure_child_logger_initialized("transport")
    return logging.getLogger("app.transport")


def get_transport_logger(name: str) -> logging.Logger:
    """Get the transport logger for network/SDK communication.

    Args:
        name: Name suffix for the logger (e.g., 'sdk' -> 'app.transport.sdk')

    Returns:
        Logger instance that writes to logs/transport_YYYYMMDD_hhmmss.log
    """
    _ensure_child_logger_initialized("transport")
    return logging.getLogger("app.transport." + name)


def get_default_client_logger() -> logging.Logger:
    """Get the client logger for client-related operations.

    Returns:
        Logger instance that writes to logs/client_YYYYMMDD_hhmmss.log
    """
    _ensure_child_logger_initialized("client")
    return logging.getLogger("app.client")


def get_client_logger(name: str) -> logging.Logger:
    """Get the client logger for client-related operations.

    Args:
        name: Name suffix for the logger (e.g., 'api' -> 'app.client.api')

    Returns:
        Logger instance that writes to logs/client_YYYYMMDD_hhmmss.log
    """
    _ensure_child_logger_initialized("client")
    return logging.getLogger("app.client." + name)


# Initialize logging when module is imported
init_logging()
