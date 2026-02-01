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
    Clear all cached deployment data.

    Returns:
        bool: True if cache was cleared successfully, False otherwise
    """
    try:
        if os.path.exists(CACHE_DIR):
            shutil.rmtree(CACHE_DIR)
            logger.info(f"Deployment cache cleared: {CACHE_DIR}")
            return True
        else:
            logger.info(f"Cache directory does not exist: {CACHE_DIR}")
            return True
    except Exception as e:
        logger.error(f"Failed to clear deployment cache: {e}")
        return False


def get_cache_stats() -> dict:
    """
    Get statistics about the deployment cache.

    Returns:
        dict: Dictionary containing:
            - exists: Whether cache directory exists
            - size_mb: Size of cache directory in MB
            - entry_count: Number of entries in cache
            - oldest_entry: Timestamp of oldest cache entry
            - newest_entry: Timestamp of newest cache entry
    """
    stats = {
        "exists": os.path.exists(CACHE_DIR),
        "size_mb": 0.0,
        "entry_count": 0,
        "oldest_entry": None,
        "newest_entry": None,
    }

    if not stats["exists"]:
        return stats

    try:
        # Calculate directory size
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(CACHE_DIR):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                total_size += os.path.getsize(filepath)
        stats["size_mb"] = round(total_size / (1024 * 1024), 2)

        # Get cache entry count and timestamps
        with Cache(CACHE_DIR) as cache:
            stats["entry_count"] = len(cache)

            if stats["entry_count"] > 0:
                # Get oldest and newest entries
                oldest_time = None
                newest_time = None

                for key in cache.iterkeys():
                    mtime = os.path.getmtime(os.path.join(CACHE_DIR, key))
                    if oldest_time is None or mtime < oldest_time:
                        oldest_time = mtime
                    if newest_time is None or mtime > newest_time:
                        newest_time = mtime

                if oldest_time:
                    stats["oldest_entry"] = datetime.fromtimestamp(
                        oldest_time
                    ).isoformat()
                if newest_time:
                    stats["newest_entry"] = datetime.fromtimestamp(
                        newest_time
                    ).isoformat()

    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")

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
