import json
from pathlib import Path

from planfile.analysis.models import ExtractedIssue, ExtractedMetric, ExtractedTask
from planfile.analysis.parsers.yaml_parser import extract_from_yaml_structure


def analyze_json(file_path: Path) -> tuple[list[ExtractedIssue], list[ExtractedMetric], list[ExtractedTask]]:
    """Analyze JSON file."""
    issues = []
    metrics = []
    tasks = []

    try:
        with open(file_path) as f:
            data = json.load(f)

        issues.extend(extract_from_yaml_structure(data, str(file_path)))

    except Exception as e:
        issues.append(ExtractedIssue(
            title=f"Fix JSON syntax in {file_path.name}",
            description=f"JSON parsing error: {str(e)}",
            priority="high",
            category="bug",
            file_path=str(file_path),
            effort_estimate="1h",
            tags=["json", "syntax"]
        ))

    return issues, metrics, tasks
