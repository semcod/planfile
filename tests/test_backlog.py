"""Tests for backlog commands."""

import pytest
import tempfile
import yaml
from pathlib import Path


def test_backlog_list_no_items():
    """Test backlog list with no items."""
    from planfile.cli.groups.backlog.commands import backlog_list
    from unittest.mock import patch
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        planfile_yaml = tmpdir_path / "planfile.yaml"
        
        # Create empty planfile.yaml
        with open(planfile_yaml, 'w') as f:
            yaml.dump({"name": "test", "project_name": "test"}, f)
        
        with patch('planfile.cli.groups.backlog.commands._get_planfile_yaml_path', return_value=planfile_yaml):
            backlog_list()
            # Should not raise an error


def test_matches_files():
    """Test _matches_files function."""
    from planfile.cli.groups.backlog.commands import _matches_files
    
    item_with_files = {"files": ["_archive/test.py", "src/main.py"]}
    assert _matches_files(item_with_files, ["_archive*"]) == True
    assert _matches_files(item_with_files, ["src/*"]) == True
    assert _matches_files(item_with_files, ["lib/*"]) == False
    
    item_without_files = {"files": []}
    assert _matches_files(item_without_files, ["_archive*"]) == False
