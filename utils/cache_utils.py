"""
Cache management utilities for deployment caching.

This module provides utilities for managing the deployment cache,
including clearing cache, getting cache stats, and monitoring cache expiration.
"""

import logging
import os
import shutil
from datetime import datetime, timedelta
from diskcache import Cache

logger = logging.getLogger(__name__)

# Cache configuration
CACHE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), ".cache", "deployments"
)


def clear_deployment_cache() -> bool:
    """
    Clear all cached deployment data using diskcache API.

    Returns:
        bool: True if cache was cleared successfully, False otherwise

    Raises:
        No exceptions - errors are logged and False is returned
    """
    try:
        with Cache(CACHE_DIR) as cache:
            cache.clear()
        logger.info(f"Deployment cache cleared: {CACHE_DIR}")
        return True
    except PermissionError as e:
        from utils.error_ids import ErrorIDs

        logger.error(
            f"Permission denied clearing cache: {e}",
            extra={"error_id": ErrorIDs.CACHE_PERMISSION_DENIED},
        )
        return False
    except OSError as e:
        from utils.error_ids import ErrorIDs

        logger.error(
            f"OS error clearing cache: {e}", extra={"error_id": ErrorIDs.CACHE_OS_ERROR}
        )
        return False
    except Exception as e:
        from utils.error_ids import ErrorIDs

        logger.error(
            f"Failed to clear deployment cache: {e}",
            extra={"error_id": ErrorIDs.CACHE_STATS_FAILED},
        )
        return False


def get_cache_stats() -> dict:
    """
    Get statistics about the deployment cache using diskcache APIs.

    Note: This function intentionally avoids accessing cache mtime directly
    as diskcache keys are hashes, not filenames. Cache size is calculated
    by iterating the cache directory structure instead.

    Returns:
        dict: Dictionary containing:
            - exists: Whether cache directory exists
            - size_mb: Size of cache directory in MB
            - entry_count: Number of entries in cache
            - has_errors: Whether errors occurred during stat collection
            - error_message: Error message if has_errors is True, None otherwise
    """
    stats = {
        "exists": os.path.exists(CACHE_DIR),
        "size_mb": 0.0,
        "entry_count": 0,
        "has_errors": False,
        "error_message": None,
    }

    if not stats["exists"]:
        return stats

    try:
        # Calculate directory size by walking the filesystem
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(CACHE_DIR):
            for filename in filenames:
                try:
                    filepath = os.path.join(dirpath, filename)
                    total_size += os.path.getsize(filepath)
                except (OSError, FileNotFoundError) as e:
                    logger.debug(f"Could not stat file {filepath}: {e}")
                    continue

        stats["size_mb"] = round(total_size / (1024 * 1024), 2)

        # Get cache entry count using diskcache API
        try:
            with Cache(CACHE_DIR) as cache:
                # Note: cache.__len__() returns the number of entries
                try:
                    stats["entry_count"] = cache.__len__()
                except (AttributeError, TypeError):
                    # Fallback: count keys manually
                    stats["entry_count"] = sum(1 for _ in cache.iterkeys())
        except Exception as e:
            logger.warning(f"Could not get cache entry count: {e}")
            # entry_count remains 0, which is safe fallback

    except PermissionError as e:
        from utils.error_ids import ErrorIDs

        logger.error(
            f"Permission denied reading cache: {e}",
            extra={"error_id": ErrorIDs.CACHE_PERMISSION_DENIED},
        )
        stats["has_errors"] = True
        stats["error_message"] = f"Permission denied: {e}"
    except OSError as e:
        from utils.error_ids import ErrorIDs

        logger.error(
            f"OS error reading cache stats: {e}",
            extra={"error_id": ErrorIDs.CACHE_OS_ERROR},
        )
        stats["has_errors"] = True
        stats["error_message"] = f"OS error: {e}"
    except Exception as e:
        from utils.error_ids import ErrorIDs

        logger.error(
            f"Failed to get cache stats: {e}",
            extra={"error_id": ErrorIDs.CACHE_STATS_FAILED},
        )
        stats["has_errors"] = True
        stats["error_message"] = str(e)

    return stats


def format_cache_expiry(expiry_seconds: int) -> str:
    """
    Format cache expiry time in seconds to human-readable format.

    Args:
        expiry_seconds: Seconds until expiry

    Returns:
        str: Human-readable format (e.g., "6d 23h 45m")
    """
    if expiry_seconds <= 0:
        return "expired"

    delta = timedelta(seconds=expiry_seconds)
    days = delta.days
    seconds = delta.seconds
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")

    return " ".join(parts) if parts else "< 1m"


def log_cache_info(cache_key: str, expiry_seconds: int = None) -> None:
    """
    Log cache information including expiry time.

    Args:
        cache_key: The cache key that was accessed
        expiry_seconds: Optional expiry time in seconds. If None, will be looked up from cache.
    """
    try:
        if expiry_seconds is None:
            with Cache(CACHE_DIR) as cache:
                expiry_seconds = int(cache.expire(cache_key) or 0)

        formatted_expiry = format_cache_expiry(expiry_seconds)
        logger.info(f"Using cache (expires in {formatted_expiry})")
    except Exception as e:
        logger.debug(f"Could not log cache info: {e}")
