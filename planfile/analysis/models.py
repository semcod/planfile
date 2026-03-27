"""
Data models for file analysis.
These dataclasses represent extracted issues, metrics, and tasks from file analysis.
"""

from dataclasses import dataclass


@dataclass
class ExtractedIssue:
    """Represents an issue extracted from a file."""
    title: str
    description: str
    priority: str  # critical, high, medium, low
    category: str  # bug, feature, refactor, test, docs, etc.
    file_path: str
    line_number: int | None = None
    effort_estimate: str | None = None
    tags: list[str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []


@dataclass
class ExtractedMetric:
    """Represents a metric extracted from a file."""
    name: str
    value: float | int | str
    threshold: float | int | str | None = None
    status: str | None = None  # good, warning, critical
    file_path: str = None


@dataclass
class ExtractedTask:
    """Represents a task extracted from a file."""
    name: str
    description: str
    type: str  # development, testing, review, documentation
    dependencies: list[str] = None
    acceptance_criteria: list[str] = None

    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []
        if self.acceptance_criteria is None:
            self.acceptance_criteria = []
