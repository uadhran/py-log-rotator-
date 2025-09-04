#!/usr/bin/env python3

import os
import glob
import gzip
import shutil
import argparse
import logging
import json
from datetime import datetime, timedelta
import subprocess  # For potential Airflow integration, but not used here

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_config(config_data=None, config_file=None):
    """Load configuration from JSON data or file."""
    if config_data:
        return json.loads(config_data)
    elif config_file:
        with open(config_file, 'r') as f:
            return json.load(f)
    else:
        raise ValueError("No configuration provided.")

def discover_logs(parent_dir, configs):
    """Discover log files in subdirectories based on configs."""
    discovered = {}
    for config in configs:
        if not config.get('enabled', True):
            continue
        parent = config['parent_directory']
        if parent_dir and parent != parent_dir:
            continue  # Filter by parent_dir if specified
        sub_configs = config['subdirectory_configs']
        for subdir, subdir_config in sub_configs.items():
            full_dir = os.path.join(parent, subdir) if subdir != 'default' else parent
            pattern = subdir_config.get('pattern', '*.log')
            files = glob.glob(os.path.join(full_dir, pattern))
            discovered[full_dir] = {
                'files': files,
                'config': subdir_config
            }
    return discovered

def rotate_log(file_path, max_size_mb, dry_run=False):
    """Rotate log if it exceeds max size."""
    size_mb = os.path.getsize(file_path) / (1024 * 1024)
    if size_mb > max_size_mb:
        rotated_path = f"{file_path}.{datetime.now().strftime('%Y%m%d%H%M%S')}"
        logger.info(f"Rotating {file_path} to {rotated_path} (size: {size_mb:.2f}MB > {max_size_mb}MB)")
        if not dry_run:
            shutil.move(file_path, rotated_path)
        return rotated_path
    return None

def compress_file(file_path, dry_run=False):
    """Compress file with gzip."""
    compressed_path = f"{file_path}.gz"
    logger.info(f"Compressing {file_path} to {compressed_path}")
    if not dry_run:
        with open(file_path, 'rb') as f_in:
            with gzip.open(compressed_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        os.remove(file_path)
    return compressed_path

def cleanup_old_logs(files, max_age_days, dry_run=False):
    """Cleanup files older than max_age_days."""
    now = datetime.now()
    deleted = []
    for file in files:
        mtime = datetime.fromtimestamp(os.path.getmtime(file))
        age_days = (now - mtime).days
        if age_days > max_age_days:
            logger.info(f"Deleting {file} (age: {age_days} days > {max_age_days} days)")
            if not dry_run:
                os.remove(file)
            deleted.append(file)
    return deleted

def generate_report(discovered, rotated, compressed, deleted, space_freed):
    """Generate a summary report."""
    report = {
        'directories_managed': len(discovered),
        'files_processed': sum(len(info['files']) for info in discovered.values()),
        'files_rotated': len(rotated),
        'files_compressed': len(compressed),
        'files_deleted': len(deleted),
        'space_freed_mb': space_freed / (1024 * 1024),
        'timestamp': datetime.now().isoformat()
    }
    return report

def process_logs(parent_dir=None, config_data=None, config_file=None, report_only=False, dry_run=False, verbose=False):
    """Main log processing function."""
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
        print(json.dumps(report, indent=2))
        return report
    
    for dir_path, info in discovered.items():
        files = info['files']
        config = info['config']
        max_size_mb = config['max_size_mb']
        max_age_days = config['max_age_days']
        
        for file in files:
            rotated_path = rotate_log(file, max_size_mb, dry_run)
            if rotated_path:
                rotated.append(rotated_path)
                comp_path = compress_file(rotated_path, dry_run)
                if comp_path:
                    compressed.append(comp_path)
                    # Calculate space freed (approx: original size - compressed size)
                    orig_size = os.path.getsize(file) if not dry_run else 0
                    comp_size = os.path.getsize(comp_path) if not dry_run else 0
                    space_freed += orig_size - comp_size
        
        # Cleanup after rotation
        updated_files = glob.glob(os.path.join(dir_path, config['pattern']))
        del_files = cleanup_old_logs(updated_files, max_age_days, dry_run)
        deleted.extend(del_files)
        space_freed += sum(os.path.getsize(f) for f in del_files if not dry_run)
    
    report = generate_report(discovered, rotated, compressed, deleted, space_freed)
    print(json.dumps(report, indent=2))
    return report

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="py-log-rotator: Log rotation and management.")
    parser.add_argument('--parent-dir', type=str, help='Parent directory containing scattered logs')
    parser.add_argument('--config-file', type=str, help='JSON configuration file')
    parser.add_argument('--report', action='store_true', help='Generate summary report only')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    parser.add_argument('--help', action='help', help='Show this help message')
    
    args = parser.parse_args()
    
    process_logs(
        parent_dir=args.parent_dir,
        config_file=args.config_file,
        report_only=args.report,
        dry_run=args.dry_run,
        verbose=args.verbose
    )
