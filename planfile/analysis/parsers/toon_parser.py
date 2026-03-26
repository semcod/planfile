import re
from pathlib import Path
from typing import Tuple, List, Any

from ..models import ExtractedIssue, ExtractedMetric, ExtractedTask
from .text_parser import analyze_text

def _parse_toon_header(line: str, file_path: Path, metrics: List[ExtractedMetric], issues: List[ExtractedIssue]) -> None:
    """Parse health and metrics tags from toon header line."""
    if 'CC̄=' in line:
        cc_match = re.search(r'CC̄=(\d+\.?\d*)', line)
        if cc_match:
            cc_value = float(cc_match.group(1))
            status = "good" if cc_value <= 3 else "warning" if cc_value <= 5 else "critical"
            metrics.append(ExtractedMetric(
                name="Average Cyclomatic Complexity",
                value=cc_value,
                threshold=3.0,
                status=status,
                file_path=str(file_path)
            ))
            
            if cc_value > 3.5:
                issues.append(ExtractedIssue(
                    title=f"Reduce average CC from {cc_value} to ≤ 3.5",
                    description="Project has high average cyclomatic complexity",
                    priority="high" if cc_value > 4.5 else "medium",
                    category="refactor",
                    file_path=str(file_path),
                    effort_estimate=f"{int((cc_value - 3.5) * 10)}h",
                    tags=["complexity", "quality"]
                ))
    
    if 'critical:' in line:
        critical_match = re.search(r'critical:(\d+)', line)
        if critical_match:
            critical_count = int(critical_match.group(1))
            metrics.append(ExtractedMetric(
                name="Critical Functions",
                value=critical_count,
                threshold=0,
                status="critical" if critical_count > 0 else "good",
                file_path=str(file_path)
            ))
            
            if critical_count > 0:
                issues.append(ExtractedIssue(
                    title=f"Refactor {critical_count} critical functions",
                    description="Functions with CC > 15 need refactoring",
                    priority="critical",
                    category="refactor",
                    file_path=str(file_path),
                    effort_estimate=f"{critical_count * 4}h",
                    tags=["complexity", "critical"]
                ))

def _parse_toon_sections(lines: List[str], file_path: Path, metrics: List[ExtractedMetric], issues: List[ExtractedIssue]) -> None:
    """Parse structural sections in toon files."""
    section_handlers = {
        'health': _parse_health_section,
        'refactor': _parse_refactor_section,
        'warnings': _parse_warnings_section,
        'errors': _parse_errors_section,
        'summary': _parse_summary_section,
        'duplicates': _parse_duplicates_section,
    }
    
    current_section = None
    for i, line in enumerate(lines):
        line = line.strip()
        
        # Determine current section
        current_section = _determine_section(line, current_section)
        
        # Parse line if we're in a section
        if current_section and current_section in section_handlers:
            section_handlers[current_section](line, i, file_path, metrics, issues)


def _determine_section(line: str, current_section: str) -> str:
    """Determine which section we're in based on the line."""
    if line.startswith('HEALTH['):
        return 'health'
    elif line.startswith('REFACTOR['):
        return 'refactor'
    elif line.startswith('WARNINGS['):
        return 'warnings'
    elif line.startswith('ERRORS['):
        return 'errors'
    elif line.startswith('SUMMARY:'):
        return 'summary'
    elif line.startswith('DUPLICATES['):
        return 'duplicates'
    elif line and not line.startswith('#') and ':' not in line and current_section:
        return None
    return current_section


def _parse_health_section(line: str, line_num: int, file_path: Path, metrics: List[ExtractedMetric], issues: List[ExtractedIssue]) -> None:
    """Parse health section for CC violations."""
    if 'CC=' in line and 'limit:' in line:
        func_match = re.search(r'(\w+)\s+CC=(\d+)', line)
        if func_match:
            func_name = func_match.group(1)
            cc_value = int(func_match.group(2))
            issues.append(ExtractedIssue(
                title=f"Refactor {func_name} (CC={cc_value})",
                description=f"Function has cyclomatic complexity {cc_value} (>15)",
                priority="critical" if cc_value > 20 else "high",
                category="refactor",
                file_path=str(file_path),
                line_number=line_num+1,
                effort_estimate=f"{max(2, cc_value // 5)}h",
                tags=["complexity", "refactor"]
            ))


def _parse_refactor_section(line: str, line_num: int, file_path: Path, metrics: List[ExtractedMetric], issues: List[ExtractedIssue]) -> None:
    """Parse refactor section."""
    # Implementation for refactor section parsing
    pass


def _parse_warnings_section(line: str, line_num: int, file_path: Path, metrics: List[ExtractedMetric], issues: List[ExtractedIssue]) -> None:
    """Parse warnings section."""
    # Implementation for warnings section parsing
    pass


def _parse_errors_section(line: str, line_num: int, file_path: Path, metrics: List[ExtractedMetric], issues: List[ExtractedIssue]) -> None:
    """Parse errors section."""
    # Implementation for errors section parsing
    pass


def _parse_summary_section(line: str, line_num: int, file_path: Path, metrics: List[ExtractedMetric], issues: List[ExtractedIssue]) -> None:
    """Parse summary section for metrics."""
    if 'files_scanned:' in line:
        files_match = re.search(r'files_scanned:\s*(\d+)', line)
        if files_match:
            metrics.append(ExtractedMetric(
                name="Files Scanned",
                value=int(files_match.group(1)),
                file_path=str(file_path)
            ))
    
    if 'dup_groups:' in line:
        dup_match = re.search(r'dup_groups:\s*(\d+)', line)
        if dup_match and int(dup_match.group(1)) > 0:
            dup_count = int(dup_match.group(1))
            metrics.append(ExtractedMetric(
                name="Duplication Groups",
                value=dup_count,
                threshold=0,
                status="warning" if dup_count > 0 else "good",
                file_path=str(file_path)
            ))
            
            issues.append(ExtractedIssue(
                title=f"Remove {dup_count} code duplication groups",
                description="Extract duplicated code into reusable functions",
                priority="medium",
                category="refactor",
                file_path=str(file_path),
                effort_estimate=f"{dup_count * 2}h",
                tags=["duplication", "cleanup"]
            ))


def _parse_duplicates_section(line: str, line_num: int, file_path: Path, metrics: List[ExtractedMetric], issues: List[ExtractedIssue]) -> None:
    """Parse duplicates section."""
    # Implementation for duplicates section parsing
    pass

def analyze_toon(file_path: Path) -> Tuple[List[ExtractedIssue], List[ExtractedMetric], List[ExtractedTask]]:
    """Analyze Toon format files with enhanced parsing."""
    issues = []
    metrics = []
    tasks = []
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        lines = content.split('\n')
        
        for line in lines[:5]:
            if line.strip() and not line.startswith('#'):
                _parse_toon_header(line, file_path, metrics, issues)
        
        _parse_toon_sections(lines, file_path, metrics, issues)
        
        text_issues, text_metrics, text_tasks = analyze_text(file_path)
        issues.extend(text_issues)
        metrics.extend(text_metrics)
        tasks.extend(text_tasks)
        
    except Exception as e:
        issues.append(ExtractedIssue(
            title=f"Failed to analyze {file_path.name}",
            description=f"Analysis error: {str(e)}",
            priority="medium",
            category="bug",
            file_path=str(file_path)
        ))
    
    return issues, metrics, tasks
