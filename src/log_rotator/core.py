#!/usr/bin/env python3
"""
Advanced Log Management System
Handles multiple log files with size-based and time-based rotation
"""

import os
import gzip
import shutil
import logging
from datetime import datetime, timedelta
from pathlib import Path
import argparse

class LogManager:
    def __init__(self, log_directory, max_size_mb=20, max_age_days=30, max_files=5):
        self.log_directory = Path(log_directory)
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.max_age_days = max_age_days
        self.max_files = max_files
        
        # Setup logging for this script
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def get_file_size(self, file_path):
        """Get file size in bytes"""
        try:
            return file_path.stat().st_size
        except OSError:
            return 0
    
    def get_file_age(self, file_path):
        """Get file age in days"""
        try:
            modified_time = datetime.fromtimestamp(file_path.stat().st_mtime)
            return (datetime.now() - modified_time).days
        except OSError:
            return 0
    
    def compress_file(self, file_path):
        """Compress file using gzip"""
        compressed_path = file_path.with_suffix(file_path.suffix + '.gz')
        
        try:
            with open(file_path, 'rb') as f_in:
                with gzip.open(compressed_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            file_path.unlink()  # Remove original file
            self.logger.info(f"Compressed: {file_path} -> {compressed_path}")
            return compressed_path
        
        except Exception as e:
            self.logger.error(f"Failed to compress {file_path}: {e}")
            return None
    
    def rotate_log(self, log_file):
        """Rotate log file with timestamp"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        rotated_name = f"{log_file.stem}_{timestamp}{log_file.suffix}"
        rotated_path = log_file.parent / rotated_name
        
        try:
            log_file.rename(rotated_path)
            
            # Create new empty log file
            log_file.touch()
            
            self.logger.info(f"Rotated: {log_file} -> {rotated_path}")
            
            # Compress the rotated file
            compressed = self.compress_file(rotated_path)
            return compressed or rotated_path
        
        except Exception as e:
            self.logger.error(f"Failed to rotate {log_file}: {e}")
            return None
    
    def clean_old_logs(self, pattern="*.log*"):
        """Remove logs older than max_age_days"""
        removed_count = 0
        
        for log_file in self.log_directory.glob(pattern):
            if self.get_file_age(log_file) > self.max_age_days:
                try:
                    log_file.unlink()
                    self.logger.info(f"Removed old log: {log_file}")
                    removed_count += 1
                except Exception as e:
                    self.logger.error(f"Failed to remove {log_file}: {e}")
        
        return removed_count
    
    def limit_log_files(self, pattern="*.log.gz"):
        """Keep only the most recent log files"""
        log_files = list(self.log_directory.glob(pattern))
        
        if len(log_files) <= self.max_files:
            return 0
        
        # Sort by modification time (newest first)
        log_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        removed_count = 0
        for old_file in log_files[self.max_files:]:
            try:
                old_file.unlink()
                self.logger.info(f"Removed excess log: {old_file}")
                removed_count += 1
            except Exception as e:
                self.logger.error(f"Failed to remove {old_file}: {e}")
        
        return removed_count
    
    def manage_single_log(self, log_file_path):
        """Manage a single log file"""
        log_file = Path(log_file_path)
        
        if not log_file.exists():
            self.logger.warning(f"Log file does not exist: {log_file}")
            return False
        
        file_size = self.get_file_size(log_file)
        size_mb = file_size / (1024 * 1024)
        
        self.logger.info(f"Checking {log_file}: {size_mb:.2f}MB")
        
        if file_size > self.max_size_bytes:
            self.logger.info(f"Log size ({size_mb:.2f}MB) exceeds limit ({self.max_size_bytes/(1024*1024)}MB)")
            return self.rotate_log(log_file) is not None
        
        return True
    
    def manage_all_logs(self, pattern="*.log"):
        """Manage all log files in the directory"""
        results = {
            'processed': 0,
            'rotated': 0,
            'cleaned': 0,
            'limited': 0
        }
        
        # Process active log files
        for log_file in self.log_directory.glob(pattern):
            results['processed'] += 1
            if self.get_file_size(log_file) > self.max_size_bytes:
                if self.rotate_log(log_file):
                    results['rotated'] += 1
        
        # Clean old logs
        results['cleaned'] = self.clean_old_logs()
        
        # Limit number of archived logs
        results['limited'] = self.limit_log_files()
        
        return results
    
    def get_directory_stats(self):
        """Get statistics about the log directory"""
        stats = {
            'total_files': 0,
            'total_size_mb': 0,
            'active_logs': 0,
            'archived_logs': 0
        }
        
        for file_path in self.log_directory.iterdir():
            if file_path.is_file():
                stats['total_files'] += 1
                stats['total_size_mb'] += self.get_file_size(file_path) / (1024 * 1024)
                
                if file_path.suffix == '.log':
                    stats['active_logs'] += 1
                elif '.log' in file_path.name:
                    stats['archived_logs'] += 1
        
        return stats

def main():
    parser = argparse.ArgumentParser(description='Advanced Log Management System')
    parser.add_argument('--log-dir', default='/var/log', help='Log directory path')
    parser.add_argument('--max-size', type=int, default=20, help='Max log size in MB')
    parser.add_argument('--max-age', type=int, default=30, help='Max log age in days')
    parser.add_argument('--max-files', type=int, default=5, help='Max archived files to keep')
    parser.add_argument('--single-file', help='Manage single log file')
    parser.add_argument('--stats', action='store_true', help='Show directory statistics')
    
    args = parser.parse_args()
    
    # Create log manager instance
    log_manager = LogManager(
        log_directory=args.log_dir,
        max_size_mb=args.max_size,
        max_age_days=args.max_age,
        max_files=args.max_files
    )
    
    if args.stats:
        stats = log_manager.get_directory_stats()
        print(f"Log Directory Statistics:")
        print(f"  Total files: {stats['total_files']}")
        print(f"  Total size: {stats['total_size_mb']:.2f} MB")
        print(f"  Active logs: {stats['active_logs']}")
        print(f"  Archived logs: {stats['archived_logs']}")
        return
    
    if args.single_file:
        # Manage single file
        success = log_manager.manage_single_log(args.single_file)
        print(f"Single file management: {'Success' if success else 'Failed'}")
    else:
        # Manage all logs in directory
        results = log_manager.manage_all_logs()
        print(f"Log management results:")
        print(f"  Files processed: {results['processed']}")
        print(f"  Files rotated: {results['rotated']}")
        print(f"  Old files cleaned: {results['cleaned']}")
        print(f"  Excess files removed: {results['limited']}")

if __name__ == "__main__":
    main()

# Example usage:
# python log_manager.py --log-dir /var/log/myapp --max-size 50 --max-age 7
# python log_manager.py --single-file /var/log/app.log
# python log_manager.py --stats
