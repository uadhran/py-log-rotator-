import pytest
from src.log_rotator.core import load_config, discover_logs

def test_load_config():
    config_data = '[{"name": "test", "parent_directory": "/tmp", "subdirectory_configs": {"default": {"max_size_mb": 10, "max_age_days": 5, "pattern": "*.log"}}, "enabled": true}]'
    config = load_config(config_data)
    assert config[0]['name'] == 'test'

def test_discover_logs(tmp_path):
    # Create temp dir structure
    parent = tmp_path / "logs"
    parent.mkdir()
    (parent / "test.log").touch()
    
    configs = [{"parent_directory": str(parent), "subdirectory_configs": {"default": {"pattern": "*.log"}}, "enabled": true}]
    discovered = discover_logs(str(parent), configs)
    assert len(discovered[str(parent)]['files']) == 1
