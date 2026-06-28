from pathlib import Path
from typing import Any

import yaml

from planfile.analysis.models import ExtractedIssue, ExtractedMetric, ExtractedTask
from planfile.analysis.parsers.text_parser import analyze_text
from planfile.analysis.parsers.toon_parser import analyze_toon


def _is_issue_content(value: str) -> bool:
    """Check if string value contains issue indicators."""
    issue_keywords = ['error', 'fail', 'bug', 'issue']
    skip_patterns = ['extractedissue', 'file_path', 'priority:', 'category:']
    if not any(keyword in value.lower() for keyword in issue_keywords):
        return False
    # Skip if this looks like our own generated issue
    return not any(skip in value.lower() for skip in skip_patterns)


def _create_issue_from_value(value: str, full_key: str, path: str) -> ExtractedIssue:
    """Create an ExtractedIssue from a string value."""
    return ExtractedIssue(
        name=f"Issue in {full_key}",
        description=value[:200],  # Limit description length
        priority="medium",
        category="bug",
        file_path=path
    )


def _process_yaml_value(value: Any, full_key: str, path: str, visited: set) -> list[ExtractedIssue]:
    """Process a single YAML value and extract issues."""
    issues = []
    # Look for common issue indicators, but not in our own generated content
    if isinstance(value, str) and len(value) < 500:  # Limit string length
        if _is_issue_content(value):
            issues.append(_create_issue_from_value(value, full_key, path))
    # Recurse with protection
    issues.extend(extract_from_yaml_structure(value, path, full_key, visited))
    return issues


def _process_yaml_dict(data: dict, path: str, parent_key: str, visited: set) -> list[ExtractedIssue]:
    """Process a YAML dict and extract issues."""
    issues = []
    for key, value in data.items():
        full_key = f"{parent_key}.{key}" if parent_key else key
        # Skip if we're already processing issues (prevent self-reference)
        if 'issues' in full_key.lower():
            continue
        issues.extend(_process_yaml_value(value, full_key, path, visited))
    return issues


def _process_yaml_list(data: list, path: str, parent_key: str, visited: set) -> list[ExtractedIssue]:
    """Process a YAML list and extract issues."""
    issues = []
    for i, item in enumerate(data):
        issues.extend(extract_from_yaml_structure(item, path, f"{parent_key}[{i}]", visited))
    return issues


def extract_from_yaml_structure(data: Any, path: str, parent_key: str = "", visited: set = None) -> list[ExtractedIssue]:
    """Extract issues from YAML structure with recursion protection."""
    if visited is None:
        visited = set()

    # Prevent infinite recursion
    if id(data) in visited:
        return []
    visited.add(id(data))

    if isinstance(data, dict):
        return _process_yaml_dict(data, path, parent_key, visited)
    elif isinstance(data, list):
        return _process_yaml_list(data, path, parent_key, visited)

    return []

def analyze_yaml(file_path: Path) -> tuple[list[ExtractedIssue], list[ExtractedMetric], list[ExtractedTask]]:
    """Analyze YAML file with better error handling."""
    issues = []
    metrics = []
    tasks = []

    try:
        with open(file_path) as f:
            content = f.read()

        try:
            data = yaml.safe_load(content)
            issues.extend(extract_from_yaml_structure(data, str(file_path)))

        except yaml.YAMLError as e:
            if 'toon' in str(file_path):
                return analyze_toon(file_path)

            issues.append(ExtractedIssue(
                name=f"Fix YAML syntax in {file_path.name}",
                description=f"YAML parsing error: {str(e)}",
                priority="high",
                category="bug",
                file_path=str(file_path),
                effort_estimate="1h",
                tags=["yaml", "syntax"]
            ))

        text_issues, text_metrics, text_tasks = analyze_text(file_path)
        issues.extend(text_issues)
        metrics.extend(text_metrics)
        tasks.extend(text_tasks)

    except Exception as e:
        issues.append(ExtractedIssue(
            name=f"Failed to parse {file_path.name}",
            description=f"File error: {str(e)}",
            priority="high",
            category="bug",
            file_path=str(file_path)
        ))

    return issues, metrics, tasks
