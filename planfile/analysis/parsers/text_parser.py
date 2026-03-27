import re
from pathlib import Path

from planfile.analysis.models import ExtractedIssue, ExtractedMetric, ExtractedTask

# Pattern matchers for common issue formats
ISSUE_PATTERNS = {
    'todo': re.compile(r'(?i)TODO\s*[:#]?\s*(.+)', re.MULTILINE),
    'fixme': re.compile(r'(?i)FIXME\s*[:#]?\s*(.+)', re.MULTILINE),
    'hack': re.compile(r'(?i)HACK\s*[:#]?\s*(.+)', re.MULTILINE),
    'bug': re.compile(r'(?i)BUG\s*[:#]?\s*(.+)', re.MULTILINE),
    'optimize': re.compile(r'(?i)OPTIMIZE\s*[:#]?\s*(.+)', re.MULTILINE),
    'refactor': re.compile(r'(?i)REFACTOR\s*[:#]?\s*(.+)', re.MULTILINE),
    'test': re.compile(r'(?i)TEST\s*[:#]?\s*(.+)', re.MULTILINE),
    'doc': re.compile(r'(?i)DOC\s*[:#]?\s*(.+)', re.MULTILINE),
}

# Metric patterns
METRIC_PATTERNS = {
    'coverage': re.compile(r'coverage[:\s=]+(\d+\.?\d*)%?', re.IGNORECASE),
    'cc': re.compile(r'CC[=_]?(\d+\.?\d*)', re.IGNORECASE),
    'complexity': re.compile(r'complexity[:\s=]+(\d+\.?\d*)', re.IGNORECASE),
    'errors': re.compile(r'errors?[:\s=]+(\d+)', re.IGNORECASE),
    'warnings': re.compile(r'warnings?[:\s=]+(\d+)', re.IGNORECASE),
    'tests': re.compile(r'tests?[:\s=]+(\d+)', re.IGNORECASE),
    'performance': re.compile(r'(\d+\.?\d*)\s*(ms|sec|s)', re.IGNORECASE),
}

def analyze_text(file_path: Path) -> tuple[list[ExtractedIssue], list[ExtractedMetric], list[ExtractedTask]]:
    """Analyze text content for TODOs, FIXMEs, and metrics."""
    issues = []
    metrics = []
    tasks = []

    try:
        with open(file_path, encoding='utf-8', errors='ignore') as f:
            content = f.read()
            lines = content.split('\n')

        # Extract issues from patterns
        for pattern_name, pattern in ISSUE_PATTERNS.items():
            for match in pattern.finditer(content):
                line_num = content[:match.start()].count('\n') + 1
                description = match.group(1).strip()

                # Determine priority based on pattern
                priority_map = {
                    'fixme': 'critical',
                    'bug': 'critical',
                    'hack': 'high',
                    'optimize': 'medium',
                    'refactor': 'medium',
                    'todo': 'medium',
                    'test': 'low',
                    'doc': 'low'
                }

                category_map = {
                    'fixme': 'bug',
                    'bug': 'bug',
                    'hack': 'technical_debt',
                    'optimize': 'performance',
                    'refactor': 'refactor',
                    'todo': 'feature',
                    'test': 'test',
                    'doc': 'documentation'
                }

                issues.append(ExtractedIssue(
                    title=f"{pattern_name.title()}: {description[:50]}...",
                    description=description,
                    priority=priority_map.get(pattern_name, 'medium'),
                    category=category_map.get(pattern_name, 'task'),
                    file_path=str(file_path),
                    line_number=line_num,
                    tags=[pattern_name]
                ))

        # Extract metrics
        for metric_name, pattern in METRIC_PATTERNS.items():
            for match in pattern.finditer(content):
                value = match.group(1)
                if metric_name == 'coverage':
                    value = float(value)
                    status = "good" if value >= 80 else "warning" if value >= 60 else "critical"
                    metrics.append(ExtractedMetric(
                        name="Test Coverage",
                        value=value,
                        threshold=80.0,
                        status=status,
                        file_path=str(file_path)
                    ))

                    if value < 80:
                        issues.append(ExtractedIssue(
                            title=f"Increase test coverage from {value}% to 80%",
                            description="Test coverage is below threshold",
                            priority="high" if value < 60 else "medium",
                            category="test",
                            file_path=str(file_path),
                            effort_estimate=f"{int((80 - value) * 0.5)}h",
                            tags=["coverage", "testing"]
                        ))
                elif metric_name == 'cc':
                    value = float(value)
                    metrics.append(ExtractedMetric(
                        name="Cyclomatic Complexity",
                        value=value,
                        threshold=10.0,
                        status="warning" if value > 10 else "good",
                        file_path=str(file_path)
                    ))

    except Exception:
        # Skip files that can't be read as text
        pass

    return issues, metrics, tasks
