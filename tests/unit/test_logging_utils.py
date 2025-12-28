"""
Unit tests for logging_utils module.
"""

import pytest
import os
import tempfile
import time
from typing import Generator
from unittest.mock import patch
from datetime import datetime, timedelta
from utils import logging_utils


class TestLoggingUtils:
    """Test cases for logging utilities."""

    @pytest.fixture
    def temp_dirs(self) -> Generator[dict[str, str], None, None]:
        """Create temporary directories for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            logs_dir = os.path.join(temp_dir, "logs")
            archive_dir = os.path.join(logs_dir, "archive")
            os.makedirs(logs_dir)
            os.makedirs(archive_dir)

            yield {
                "temp_dir": temp_dir,
                "logs_dir": logs_dir,
                "archive_dir": archive_dir,
            }

    def test_gzip_file(self, temp_dirs: dict[str, str]) -> None:
        """Test _gzip_file function."""
        # Create a test file
        test_file = os.path.join(temp_dirs["logs_dir"], "test.log")
        test_content = b"Test log content\n"

        with open(test_file, "wb") as f:
            f.write(test_content)

        # Gzip the file
        gzipped_file = os.path.join(temp_dirs["logs_dir"], "test.log.gz")
        logging_utils._gzip_file(test_file, gzipped_file)

        # Verify original file is removed
        assert not os.path.exists(test_file)

        # Verify gzipped file exists and contains correct content
        assert os.path.exists(gzipped_file)

        import gzip

        with gzip.open(gzipped_file, "rb") as f:
            content = f.read()
        assert content == test_content

    @patch("utils.logging_utils._loggers_initialized", False)
    @patch("utils.logging_utils._log_timestamp", None)
    @patch("utils.logging_utils._child_loggers_setup", set())
    def test_init_logging_archives_old_logs(self, temp_dirs: dict[str, str]) -> None:
        """Test that init_logging gzips old log files when moving to archive."""
        # Create log files with different ages
        old_log = os.path.join(temp_dirs["logs_dir"], "old.log")
        new_log = os.path.join(temp_dirs["logs_dir"], "new.log")

        # Write some content
        with open(old_log, "w") as f:
            f.write("old log content")
        with open(new_log, "w") as f:
            f.write("new log content")

        # Set modification times: old file is 25 hours old, new is 1 hour old
        old_time = time.time() - (25 * 3600)
        new_time = time.time() - (1 * 3600)
        os.utime(old_log, (old_time, old_time))
        os.utime(new_log, (new_time, new_time))

        with (
            patch("utils.logging_utils.DEFAULT_LOG_FOLDER", temp_dirs["logs_dir"]),
            patch("utils.logging_utils.os.path.exists", return_value=True),
            patch("utils.logging_utils.os.makedirs"),
            patch("logging.basicConfig"),
            patch("logging.getLogger"),
        ):
            logging_utils.init_logging(debug=True)

            # Check the archive directory contents after init_logging
            archive_files = os.listdir(temp_dirs["archive_dir"])
            assert "old.log.gz" in archive_files  # Old file should be gzipped
            assert (
                "new.log" in archive_files
            )  # New file should be moved without gzipping

    @patch("utils.logging_utils._loggers_initialized", False)
    @patch("utils.logging_utils._log_timestamp", None)
    @patch("utils.logging_utils._child_loggers_setup", set())
    def test_init_logging_archives_new_logs_no_gzip(
        self, temp_dirs: dict[str, str]
    ) -> None:
        """Test that init_logging moves new log files without gzipping."""
        # Create a new log file (<24h old)
        new_log = os.path.join(temp_dirs["logs_dir"], "recent.log")

        with open(new_log, "w") as f:
            f.write("recent log content")

        # Set modification time to 1 hour ago
        recent_time = time.time() - (1 * 3600)
        os.utime(new_log, (recent_time, recent_time))

        with (
            patch("utils.logging_utils.DEFAULT_LOG_FOLDER", temp_dirs["logs_dir"]),
            patch("utils.logging_utils.os.path.exists", return_value=True),
            patch("utils.logging_utils.os.makedirs"),
            patch("logging.basicConfig"),
            patch("logging.getLogger"),
        ):
            logging_utils.init_logging(debug=True)

            # Check that file was moved without gzipping
            archive_files = os.listdir(temp_dirs["archive_dir"])
            assert "recent.log" in archive_files

    @patch("utils.logging_utils._loggers_initialized", False)
    @patch("utils.logging_utils._log_timestamp", None)
    @patch("utils.logging_utils._child_loggers_setup", set())
    def test_init_logging_gzips_old_archive_logs(
        self, temp_dirs: dict[str, str]
    ) -> None:
        """Test that init_logging gzips old logs already in archive."""
        # Create an old log file in archive directory
        old_archive_log = os.path.join(temp_dirs["archive_dir"], "old_in_archive.log")

        with open(old_archive_log, "w") as f:
            f.write("old archive log content")

        # Set modification time to 25 hours ago
        old_time = time.time() - (25 * 3600)
        os.utime(old_archive_log, (old_time, old_time))

        with (
            patch("utils.logging_utils.DEFAULT_LOG_FOLDER", temp_dirs["logs_dir"]),
            patch("utils.logging_utils.os.path.exists", return_value=True),
            patch("utils.logging_utils.os.makedirs"),
            patch("logging.basicConfig"),
            patch("logging.getLogger"),
            patch("utils.logging_utils.datetime") as mock_datetime,
        ):
            mock_datetime.now.return_value = datetime.fromtimestamp(time.time())
            mock_datetime.fromtimestamp = datetime.fromtimestamp
            mock_datetime.timedelta = timedelta

            logging_utils.init_logging(debug=True)

            # Check that old archive log was gzipped
            archive_files = os.listdir(temp_dirs["archive_dir"])
            assert "old_in_archive.log.gz" in archive_files
            assert "old_in_archive.log" not in archive_files

    def test_get_default_server_logger(self) -> None:
        """Test getting default server logger."""
        logger = logging_utils.get_default_server_logger()
        assert logger.name == "app.server"
        assert hasattr(logger, "info")  # Should have logging methods

    def test_get_server_logger_with_suffix(self) -> None:
        """Test getting server logger with suffix."""
        logger = logging_utils.get_server_logger("routes")
        assert logger.name == "app.server.routes"

    def test_get_default_transport_logger(self) -> None:
        """Test getting default transport logger."""
        logger = logging_utils.get_default_transport_logger()
        assert logger.name == "app.transport"

    def test_get_transport_logger_with_suffix(self) -> None:
        """Test getting transport logger with suffix."""
        logger = logging_utils.get_transport_logger("sdk")
        assert logger.name == "app.transport.sdk"

    def test_get_default_client_logger(self) -> None:
        """Test getting default client logger."""
        logger = logging_utils.get_default_client_logger()
        assert logger.name == "app.client"

    def test_get_client_logger_with_suffix(self) -> None:
        """Test getting client logger with suffix."""
        logger = logging_utils.get_client_logger("api")
        assert logger.name == "app.client.api"

    @patch("utils.logging_utils._loggers_initialized", False)
    @patch("utils.logging_utils._log_timestamp", None)
    @patch("utils.logging_utils._child_loggers_setup", set())
    def test_init_logging_idempotent(self) -> None:
        """Test that init_logging is idempotent."""
        with (
            patch("utils.logging_utils.os.path.exists", return_value=True),
            patch("utils.logging_utils.os.makedirs"),
            patch("logging.basicConfig"),
            patch("logging.getLogger"),
        ):
            # First call
            logging_utils.init_logging(debug=True)
            # Second call should not fail
            logging_utils.init_logging(debug=True)
