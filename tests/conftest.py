"""Pytest fixtures for log_rotator tests."""

import os
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
import pytest
import sys

PROJECT_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if PROJECT_SRC not in sys.path:
    sys.path.insert(0, PROJECT_SRC)


@pytest.fixture
def temp_dir(tmp_path):
    """Create a temporary directory for testing."""
    test_dir = tmp_path / "test_logs"
    test_dir.mkdir()
    yield test_dir
    # Cleanup is automatic with tmp_path


@pytest.fixture
def sample_log_file(temp_dir):
    """Create a sample log file."""
    log_file = temp_dir / "app.log"
    log_file.write_text("Line 1\nLine 2\nLine 3\n" * 1000)  # Create a log file with content
    return str(log_file)


@pytest.fixture
def large_log_file(temp_dir):
    """Create a large log file (>1MB)."""
    log_file = temp_dir / "large.log"
    # Create a file > 1MB
    content = "This is a log line with some content.\n" * 50000
    log_file.write_text(content)
    return str(log_file)


@pytest.fixture
def old_log_file(temp_dir):
    """Create an old log file."""
    log_file = temp_dir / "old.log"
    log_file.write_text("Old log content\n")

    # Set modification time to 60 days ago
    old_time = (datetime.now() - timedelta(days=60)).timestamp()
    os.utime(str(log_file), (old_time, old_time))

    return str(log_file)


@pytest.fixture
def sample_config():
    """Return a sample configuration dictionary."""
    return [
        {
            "parent_directory": "/tmp/test_logs",
            "enabled": True,
            "subdirectory_configs": {
                "default": {
                    "pattern": "*.log",
                    "max_size_mb": 1,
                    "max_age_days": 30
                }
            }
        }
    ]


@pytest.fixture
def sample_config_json(temp_dir):
    """Create a sample configuration JSON file."""
    config = [
        {
            "parent_directory": str(temp_dir),
            "enabled": True,
            "subdirectory_configs": {
                "default": {
                    "pattern": "*.log",
                    "max_size_mb": 1,
                    "max_age_days": 30
                }
            }
        }
    ]

    config_file = temp_dir / "config.json"
    config_file.write_text(json.dumps(config, indent=2))

    return str(config_file)


@pytest.fixture
def invalid_json_file(temp_dir):
    """Create an invalid JSON file."""
    invalid_file = temp_dir / "invalid.json"
    invalid_file.write_text("{ invalid json content")
    return str(invalid_file)


@pytest.fixture
def nested_log_structure(temp_dir):
    """Create a nested directory structure with log files."""
    # Create subdirectories
    app_dir = temp_dir / "app"
    db_dir = temp_dir / "database"
    app_dir.mkdir()
    db_dir.mkdir()

    # Create log files
    (app_dir / "app.log").write_text("App log content\n" * 100)
    (app_dir / "app.log.old").write_text("Old app log\n")
    (db_dir / "db.log").write_text("Database log content\n" * 100)

    return {
        "parent": str(temp_dir),
        "app_dir": str(app_dir),
        "db_dir": str(db_dir),
    }


@pytest.fixture
def mock_config_for_nested(nested_log_structure):
    """Configuration for nested log structure."""
    return [
        {
            "parent_directory": nested_log_structure["parent"],
            "enabled": True,
            "subdirectory_configs": {
                "app": {
                    "pattern": "*.log",
                    "max_size_mb": 0.001,  # Very small for testing
                    "max_age_days": 30
                },
                "database": {
                    "pattern": "*.log",
                    "max_size_mb": 0.001,
                    "max_age_days": 30
                }
            }
        }
    ]


@pytest.fixture(autouse=True)
def reset_logging():
    """Reset logging configuration after each test."""
    import logging
    yield
    # Reset logging level
    logging.getLogger("log_rotator.core").setLevel(logging.INFO)
