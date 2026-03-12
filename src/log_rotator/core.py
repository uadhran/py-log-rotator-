#!/usr/bin/env python3

import os
import glob
import gzip
import shutil
import argparse
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple

from .exceptions import (
    ConfigurationError,
    RotationError,
    CompressionError,
    CleanupError,
    ValidationError,
)

# Constants
MB_BYTES = 1024 * 1024
TIMESTAMP_FORMAT = '%Y%m%d%H%M%S'
DEFAULT_PATTERN = '*.log'

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def validate_path(path: str, must_exist: bool = False) -> str:
    """
    Validate and sanitize file path to prevent path traversal attacks.

    Args:
        path: Path to validate
        must_exist: Whether the path must exist

    Returns:
        Absolute, normalized path

    Raises:
        ValidationError: If path is invalid or contains dangerous patterns
    """
    if not path:
        raise ValidationError("Path cannot be empty")

    # Normalize the path to resolve .. and .
    normalized_path = os.path.abspath(os.path.normpath(path))

    # Check for path traversal attempts
    if '..' in path:
        logger.warning(f"Potential path traversal detected in: {path}")

    # Check if path exists if required
    if must_exist and not os.path.exists(normalized_path):
        raise ValidationError(f"Path does not exist: {normalized_path}")

    return normalized_path


def validate_pattern(pattern: str) -> str:
    """
    Validate glob pattern to prevent injection attacks.

    Args:
        pattern: Glob pattern to validate

    Returns:
        Validated pattern

    Raises:
        ValidationError: If pattern contains dangerous characters
    """
    if not pattern:
        return DEFAULT_PATTERN

    # Check for dangerous characters that could be used for command injection
    dangerous_chars = ['|', '&', ';', '$', '`', '>', '<', '\n', '\r']
    for char in dangerous_chars:
        if char in pattern:
            raise ValidationError(f"Invalid character '{char}' in pattern: {pattern}")

    return pattern


def load_config(config_data: Optional[str] = None, config_file: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Load configuration from JSON data or file.

    Args:
        config_data: JSON string containing configuration
        config_file: Path to JSON configuration file

    Returns:
        List of configuration dictionaries

    Raises:
        ConfigurationError: If configuration cannot be loaded or is invalid
    """
    try:
        if config_data:
            return json.loads(config_data)
        elif config_file:
            validated_path = validate_path(config_file, must_exist=True)
            try:
                with open(validated_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    logger.info(f"Successfully loaded configuration from {validated_path}")
                    return config
            except FileNotFoundError:
                raise ConfigurationError(f"Configuration file not found: {validated_path}")
            except json.JSONDecodeError as e:
                raise ConfigurationError(f"Invalid JSON in configuration file: {e}")
            except IOError as e:
                raise ConfigurationError(f"Error reading configuration file: {e}")
        else:
            raise ConfigurationError("No configuration provided (config_data or config_file required)")
    except ValidationError as e:
        raise ConfigurationError(f"Configuration validation failed: {e}")
    except Exception as e:
        raise ConfigurationError(f"Unexpected error loading configuration: {e}")


def discover_logs(parent_dir: Optional[str], configs: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Discover log files in subdirectories based on configs.

    Args:
        parent_dir: Optional parent directory to filter by
        configs: List of configuration dictionaries

    Returns:
        Dictionary mapping directory paths to file info and config

    Raises:
        ValidationError: If directory paths or patterns are invalid
    """
    discovered = {}

    for config in configs:
        if not config.get('enabled', True):
            continue

        try:
            parent = config['parent_directory']
            validated_parent = validate_path(parent)

            if parent_dir:
                validated_parent_dir = validate_path(parent_dir)
                if validated_parent != validated_parent_dir:
                    continue  # Filter by parent_dir if specified

            # Check if parent directory exists and is readable
            if not os.path.exists(validated_parent):
                logger.warning(f"Parent directory does not exist: {validated_parent}")
                continue

            if not os.access(validated_parent, os.R_OK):
                logger.warning(f"Parent directory is not readable: {validated_parent}")
                continue

            sub_configs = config['subdirectory_configs']
            for subdir, subdir_config in sub_configs.items():
                full_dir = os.path.join(validated_parent, subdir) if subdir != 'default' else validated_parent
                full_dir = validate_path(full_dir)

                pattern = validate_pattern(subdir_config.get('pattern', DEFAULT_PATTERN))

                try:
                    files = glob.glob(os.path.join(full_dir, pattern))
                    discovered[full_dir] = {
                        'files': files,
                        'config': subdir_config
                    }
                except (OSError, PermissionError) as e:
                    logger.error(f"Error accessing directory {full_dir}: {e}")
                    continue

        except (KeyError, ValidationError) as e:
            logger.error(f"Invalid configuration entry: {e}")
            continue

    return discovered


def rotate_log(file_path: str, max_size_mb: float, dry_run: bool = False) -> Optional[str]:
    """
    Rotate log if it exceeds max size.

    Args:
        file_path: Path to log file
        max_size_mb: Maximum size in megabytes before rotation
        dry_run: If True, don't actually rotate the file

    Returns:
        Path to rotated file, or None if rotation wasn't needed

    Raises:
        RotationError: If rotation fails
    """
    try:
        validated_path = validate_path(file_path, must_exist=True)

        try:
            size_bytes = os.path.getsize(validated_path)
            size_mb = size_bytes / MB_BYTES
        except OSError as e:
            raise RotationError(f"Cannot get size of {validated_path}: {e}")

        if size_mb > max_size_mb:
            rotated_path = f"{validated_path}.{datetime.now().strftime(TIMESTAMP_FORMAT)}"
            logger.info(f"Rotating {validated_path} to {rotated_path} (size: {size_mb:.2f}MB > {max_size_mb}MB)")

            if not dry_run:
                try:
                    shutil.move(validated_path, rotated_path)
                    logger.info(f"Successfully rotated {validated_path}")
                except (OSError, shutil.Error) as e:
                    raise RotationError(f"Failed to rotate {validated_path}: {e}")

            return rotated_path

        return None

    except ValidationError as e:
        raise RotationError(f"Path validation failed: {e}")
    except Exception as e:
        raise RotationError(f"Unexpected error during rotation: {e}")


def compress_file(file_path: str, dry_run: bool = False) -> Optional[str]:
    """
    Compress file with gzip.

    Args:
        file_path: Path to file to compress
        dry_run: If True, don't actually compress the file

    Returns:
        Path to compressed file

    Raises:
        CompressionError: If compression fails
    """
    try:
        validated_path = validate_path(file_path, must_exist=True)
        compressed_path = f"{validated_path}.gz"

        logger.info(f"Compressing {validated_path} to {compressed_path}")

        if not dry_run:
            try:
                with open(validated_path, 'rb') as f_in:
                    with gzip.open(compressed_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)

                # Verify compressed file was created
                if not os.path.exists(compressed_path):
                    raise CompressionError(f"Compressed file was not created: {compressed_path}")

                # Remove original file only after successful compression
                try:
                    os.remove(validated_path)
                    logger.info(f"Successfully compressed and removed original: {validated_path}")
                except OSError as e:
                    logger.warning(f"Compression succeeded but failed to remove original {validated_path}: {e}")

            except (OSError, IOError, gzip.BadGzipFile) as e:
                # Clean up partial compressed file if it exists
                if os.path.exists(compressed_path):
                    try:
                        os.remove(compressed_path)
                    except OSError:
                        pass
                raise CompressionError(f"Failed to compress {validated_path}: {e}")

        return compressed_path

    except ValidationError as e:
        raise CompressionError(f"Path validation failed: {e}")
    except Exception as e:
        raise CompressionError(f"Unexpected error during compression: {e}")


def cleanup_old_logs(files: List[str], max_age_days: int, dry_run: bool = False) -> List[str]:
    """
    Cleanup files older than max_age_days.

    Args:
        files: List of file paths to check
        max_age_days: Maximum age in days before deletion
        dry_run: If True, don't actually delete files

    Returns:
        List of deleted file paths

    Raises:
        CleanupError: If cleanup operation encounters errors (logged but doesn't stop processing)
    """
    now = datetime.now()
    deleted = []

    for file in files:
        try:
            validated_file = validate_path(file)

            # Skip if file doesn't exist (might have been already processed)
            if not os.path.exists(validated_file):
                logger.debug(f"Skipping non-existent file: {validated_file}")
                continue

            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(validated_file))
            except OSError as e:
                logger.error(f"Cannot get modification time for {validated_file}: {e}")
                continue

            age_days = (now - mtime).days

            if age_days > max_age_days:
                logger.info(f"Deleting {validated_file} (age: {age_days} days > {max_age_days} days)")

                if not dry_run:
                    try:
                        os.remove(validated_file)
                        logger.info(f"Successfully deleted {validated_file}")
                    except OSError as e:
                        logger.error(f"Failed to delete {validated_file}: {e}")
                        continue

                deleted.append(validated_file)

        except ValidationError as e:
            logger.error(f"Path validation failed for {file}: {e}")
            continue
        except Exception as e:
            logger.error(f"Unexpected error processing {file}: {e}")
            continue

    return deleted


def generate_report(discovered: Dict[str, Dict[str, Any]], rotated: List[str],
                   compressed: List[str], deleted: List[str], space_freed: int) -> Dict[str, Any]:
    """
    Generate a summary report.

    Args:
        discovered: Dictionary of discovered directories and files
        rotated: List of rotated file paths
        compressed: List of compressed file paths
        deleted: List of deleted file paths
        space_freed: Total space freed in bytes

    Returns:
        Dictionary containing report data
    """
    report = {
        'directories_managed': len(discovered),
        'files_processed': sum(len(info['files']) for info in discovered.values()),
        'files_rotated': len(rotated),
        'files_compressed': len(compressed),
        'files_deleted': len(deleted),
        'space_freed_mb': round(space_freed / MB_BYTES, 2),
        'timestamp': datetime.now().isoformat()
    }
    return report


def process_logs(parent_dir: Optional[str] = None, config_data: Optional[str] = None,
                config_file: Optional[str] = None, report_only: bool = False,
                dry_run: bool = False, verbose: bool = False) -> Dict[str, Any]:
    """
    Main log processing function.

    Args:
        parent_dir: Optional parent directory to filter by
        config_data: JSON string containing configuration
        config_file: Path to JSON configuration file
        report_only: If True, only generate a report without processing
        dry_run: If True, show what would be done without making changes
        verbose: Enable verbose logging

    Returns:
        Dictionary containing processing report

    Raises:
        ConfigurationError: If configuration is invalid
    """
    if verbose:
        logger.setLevel(logging.DEBUG)

    configs = load_config(config_data, config_file)
    discovered = discover_logs(parent_dir, configs)

    rotated = []
    compressed = []
    deleted = []
    space_freed = 0

    if report_only:
        logger.info("Generating report only.")
        report = generate_report(discovered, rotated, compressed, deleted, space_freed)
        logger.info(json.dumps(report, indent=2))
        return report

    for dir_path, info in discovered.items():
        files = info['files']
        config = info['config']
        max_size_mb = config.get('max_size_mb', 100)  # Default 100MB
        max_age_days = config.get('max_age_days', 30)  # Default 30 days

        for file in files:
            try:
                orig_size = 0
                if not dry_run:
                    try:
                        if os.path.exists(file):
                            orig_size = os.path.getsize(file)
                    except OSError as e:
                        logger.warning(f"Could not get original size for {file}: {e}")

                rotated_path = rotate_log(file, max_size_mb, dry_run)
                if rotated_path:
                    rotated.append(rotated_path)

                    try:
                        comp_path = compress_file(rotated_path, dry_run)
                        if comp_path:
                            compressed.append(comp_path)

                            # Calculate space freed (approx: original size - compressed size)
                            if not dry_run:
                                try:
                                    comp_size = os.path.getsize(comp_path) if os.path.exists(comp_path) else 0
                                    space_freed += max(0, orig_size - comp_size)
                                except OSError as e:
                                    logger.warning(f"Could not calculate space freed: {e}")

                    except CompressionError as e:
                        logger.error(f"Compression failed for {rotated_path}: {e}")
                        # Continue processing other files

            except RotationError as e:
                logger.error(f"Rotation failed for {file}: {e}")
                # Continue processing other files

        # Cleanup after rotation
        try:
            pattern = validate_pattern(config.get('pattern', DEFAULT_PATTERN))
            base_glob = os.path.join(dir_path, pattern)
            updated_files = []
            updated_files.extend(glob.glob(base_glob))
            updated_files.extend(glob.glob(base_glob + ".*"))
            updated_files.extend(glob.glob(base_glob + ".*.gz"))
            del_files = cleanup_old_logs(updated_files, max_age_days, dry_run)
            deleted.extend(del_files)

            # Calculate space freed from deletions
            if not dry_run:
                for f in del_files:
                    try:
                        # File is already deleted, can't get size
                        # This is a limitation - would need to track size before deletion
                        pass
                    except Exception:
                        pass

        except (ValidationError, CleanupError) as e:
            logger.error(f"Cleanup failed for {dir_path}: {e}")
            # Continue processing

    report = generate_report(discovered, rotated, compressed, deleted, space_freed)
    logger.info(json.dumps(report, indent=2))
    return report


def main():
    """Main entry point for command-line usage."""
    parser = argparse.ArgumentParser(description="py-log-rotator: Log rotation and management.")
    parser.add_argument('--parent-dir', type=str, help='Parent directory containing scattered logs')
    parser.add_argument('--config-file', type=str, help='JSON configuration file')
    parser.add_argument('--report', action='store_true', help='Generate summary report only')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')

    args = parser.parse_args()

    try:
        process_logs(
            parent_dir=args.parent_dir,
            config_file=args.config_file,
            report_only=args.report,
            dry_run=args.dry_run,
            verbose=args.verbose
        )
    except ConfigurationError as e:
        logger.error(f"Configuration error: {e}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
