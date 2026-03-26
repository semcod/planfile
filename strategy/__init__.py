"""
Strategy package - Strategic PM layer for ticket systems.

This package provides:
- Strategy and sprint modeling in YAML
- Integration with external ticket systems (Jira, GitHub, GitLab)
- CLI and API for applying and reviewing strategies
"""

__version__ = "0.1.1"
__author__ = "Tom Sapletta"
__email__ = "tom@sapletta.com"

from .models import Strategy, Sprint, TaskPattern, TaskType, ModelHints, ModelTier

__all__ = [
    "Strategy",
    "Sprint", 
    "TaskPattern",
    "TaskType",
    "ModelHints",
    "ModelTier",
]
