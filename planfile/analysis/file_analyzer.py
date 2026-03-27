"""
File analysis module for planfile generation.
Extracts issues, metrics, and tasks from various file formats.
"""

from pathlib import Path
from typing import Any

from planfile.analysis.models import ExtractedIssue, ExtractedMetric, ExtractedTask
from planfile.analysis.parsers.json_parser import analyze_json
from planfile.analysis.parsers.text_parser import analyze_text
from planfile.analysis.parsers.toon_parser import analyze_toon
from planfile.analysis.parsers.yaml_parser import analyze_yaml, extract_from_yaml_structure


class FileAnalyzer:
    """Analyzes YAML/JSON files to extract issues and metrics."""

    def __init__(self):
        self.extractors = {
            '.yaml': analyze_yaml,
            '.yml': analyze_yaml,
            '.json': analyze_json,
            '.toon.yaml': analyze_toon,
            '.toon.yml': analyze_toon,
        }

    def analyze_file(self, file_path: Path) -> tuple[list[ExtractedIssue], list[ExtractedMetric], list[ExtractedTask]]:
        """Analyze a single file and extract issues, metrics, and tasks."""
        issues = []
        metrics = []
        tasks = []

        # Get file extension
        ext = ''.join(file_path.suffixes)

        # Find appropriate analyzer
        analyzer = None
        for pattern, func in self.extractors.items():
            if ext.endswith(pattern):
                analyzer = func
                break

        if not analyzer:
            # Default text analysis
            issues, metrics, tasks = analyze_text(file_path)
        else:
            issues, metrics, tasks = analyzer(file_path)

        return issues, metrics, tasks

    def _analyze_toon(self, file_path: Path):
        return analyze_toon(file_path)

    def _analyze_yaml(self, file_path: Path):
        return analyze_yaml(file_path)

    def _analyze_json(self, file_path: Path):
        return analyze_json(file_path)

    def _analyze_text(self, file_path: Path):
        return analyze_text(file_path)

    def _extract_from_yaml_structure(self, data: Any, path: str, parent_key: str = ""):
        return extract_from_yaml_structure(data, path, parent_key)

    def _extract_from_json_structure(self, data: Any, path: str, parent_key: str = ""):
        return extract_from_yaml_structure(data, path, parent_key)

    def analyze_directory(self, directory: Path, patterns: list[str] = None) -> dict[str, Any]:
        """Analyze all matching files in directory."""
        if patterns is None:
            patterns = ['*.yaml', '*.yml', '*.json', '*.toon.yaml', '*.toon.yml']

        all_issues = []
        all_metrics = []
        all_tasks = []
        analyzed_files = []

        for pattern in patterns:
            for file_path in directory.rglob(pattern):
                # Skip hidden files and common exclusions
                if file_path.name.startswith('.') or any(skip in str(file_path) for skip in ['__pycache__', '.git', 'node_modules', '.pytest_cache', '.planfile_analysis']):
                    continue

                # Skip analysis files to prevent recursive analysis
                if 'analysis_summary.json' in file_path.name or 'local-strategy.yaml' in file_path.name:
                    continue

                issues, metrics, tasks = self.analyze_file(file_path)

                all_issues.extend(issues)
                all_metrics.extend(metrics)
                all_tasks.extend(tasks)
                analyzed_files.append(str(file_path))

        return {
            'issues': all_issues,
            'metrics': all_metrics,
            'tasks': all_tasks,
            'analyzed_files': analyzed_files,
            'summary': self._generate_summary(all_issues, all_metrics, all_tasks)
        }

    def _generate_summary(self, issues: list[ExtractedIssue], metrics: list[ExtractedMetric], tasks: list[ExtractedTask]) -> dict[str, Any]:
        """Generate summary statistics."""
        # Count by priority
        priority_counts = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}
        for issue in issues:
            priority_counts[issue.priority] = priority_counts.get(issue.priority, 0) + 1

        # Count by category
        category_counts = {}
        for issue in issues:
            category_counts[issue.category] = category_counts.get(issue.category, 0) + 1

        # Critical metrics
        critical_metrics = [m for m in metrics if m.status == 'critical']

        return {
            'total_issues': len(issues),
            'priority_breakdown': priority_counts,
            'category_breakdown': category_counts,
            'total_metrics': len(metrics),
            'critical_metrics': len(critical_metrics),
            'total_tasks': len(tasks)
        }
