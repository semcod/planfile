"""Utility functions for sync operations."""

from __future__ import annotations

import yaml


def save_v1_format(file_path: str, data: dict) -> None:
    """Save data back to v1 format YAML file."""
    with open(file_path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
