"""
Data models for file analysis.
These dataclasses represent extracted issues, metrics, and tasks from file analysis.
"""

from dataclasses import dataclass, field


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
    tags: list[str] = field(default_factory=list)


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
    dependencies: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
