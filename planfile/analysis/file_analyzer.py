"""
File analysis module for planfile generation.
Extracts issues, metrics, and tasks from various file formats.
"""

import os
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from planfile.analysis.models import ExtractedIssue, ExtractedMetric, ExtractedTask
from planfile.analysis.parsers.json_parser import analyze_json
from planfile.analysis.parsers.text_parser import analyze_text
from planfile.analysis.parsers.toon_parser import analyze_toon
from planfile.analysis.parsers.yaml_parser import analyze_yaml, extract_from_yaml_structure

try:
    from planfile_analyzer import HAS_RUST_ANALYZER
    from planfile_analyzer import analyze_file as _native_analyze_file
except ImportError:
    HAS_RUST_ANALYZER = False
    _native_analyze_file = None


class FileAnalyzer:
    """Analyzes YAML/JSON files to extract issues and metrics."""

    DEFAULT_MAX_SINGLE_FILE_BYTES: int = 1_048_576  # 1 MB

    #: Directory names that never contain first-party source. Matched against the
    #: parts of each path, so a vendored tree is skipped wherever it is nested.
    EXCLUDED_DIRS = frozenset({
        '__pycache__', '.git', 'node_modules', '.pytest_cache', '.planfile_analysis',
        '.venv', 'venv', '.env', 'site-packages', 'vendor', 'third_party',
        'dist', 'build', '.tox', '.nox', '.mypy_cache', '.ruff_cache',
        'htmlcov', '.coverage', 'coverage', '.cache', '.gradle', 'target',
        '.terraform', '.next', '.nuxt', '.svelte-kit', 'bower_components',
        '.subactor', '.worktrees', '.planfile', '.governance', '.intent',
        '.cursor', 'analyses',
    })

    #: Suffixes of directory names that never contain first-party source.
    EXCLUDED_DIR_SUFFIXES = ('.egg-info',)

    @classmethod
    def is_excluded(cls, file_path: Path, root: Path | None = None) -> bool:
        """True if *file_path* lives inside a directory we must not analyze.

        Only the part of the path below *root* is inspected, so a project that
        merely happens to live under e.g. ~/build is still analyzed.
        """
        try:
            parts = file_path.relative_to(root).parts if root else file_path.parts
        except ValueError:
            parts = file_path.parts
        for part in parts[:-1]:
            if part in cls.EXCLUDED_DIRS or part.endswith(cls.EXCLUDED_DIR_SUFFIXES):
                return True
        return False

    def __init__(self):
        self.extractors = {
            '.toon.yaml': analyze_toon,
            '.toon.yml': analyze_toon,
            '.yaml': analyze_yaml,
            '.yml': analyze_yaml,
            '.json': analyze_json,
        }

    def analyze_file(
        self,
        file_path: Path,
        *,
        max_single_file_bytes: int | None = DEFAULT_MAX_SINGLE_FILE_BYTES,
    ) -> tuple[list[ExtractedIssue], list[ExtractedMetric], list[ExtractedTask]]:
        """Analyze a single file and extract issues, metrics, and tasks."""
        if max_single_file_bytes is not None:
            try:
                file_size = file_path.stat().st_size
                if file_size > max_single_file_bytes:
                    return (
                        [
                            ExtractedIssue(
                                name=f"File exceeds analysis size limit in {file_path.name}",
                                description=(
                                    f"File {file_path.name} exceeds maximum single file analysis size "
                                    f"of {max_single_file_bytes} bytes ({file_size} bytes) and was skipped."
                                ),
                                priority="medium",
                                category="health",
                                file_path=str(file_path),
                                tags=["oversized", "skipped"],
                            )
                        ],
                        [],
                        [],
                    )
            except OSError:
                pass

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

        try:
            if not analyzer:
                if HAS_RUST_ANALYZER and _native_analyze_file is not None:
                    try:
                        raw_issues, raw_metrics, raw_tasks = _native_analyze_file(file_path)
                        issues = [ExtractedIssue(**i) for i in raw_issues]
                        metrics = [ExtractedMetric(**m) for m in raw_metrics]
                        tasks = [ExtractedTask(**t) for t in raw_tasks]
                        return issues, metrics, tasks
                    except TimeoutError:
                        raise
                    except Exception:
                        pass
                # Default text analysis
                issues, metrics, tasks = analyze_text(file_path)
            else:
                issues, metrics, tasks = analyzer(file_path)
        except TimeoutError:
            raise

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

    def analyze_directory(
        self,
        directory: Path,
        patterns: list[str] | None = None,
        *,
        max_files: int | None = None,
        max_bytes: int | None = None,
        max_single_file_bytes: int | None = DEFAULT_MAX_SINGLE_FILE_BYTES,
    ) -> dict[str, Any]:
        """Analyze matching files without exceeding optional read budgets.

        The analyzer is read-only. Limits are enforced before opening each
        file, and the result records whether the view was truncated so callers
        can fail closed instead of presenting a partial health report as
        complete.
        """
        if max_files is not None and max_files < 1:
            raise ValueError("max_files must be positive")
        if max_bytes is not None and max_bytes < 1:
            raise ValueError("max_bytes must be positive")
        if max_single_file_bytes is not None and max_single_file_bytes < 1:
            raise ValueError("max_single_file_bytes must be positive")

        directory = Path(directory)
        if directory.is_file():
            issues, metrics, tasks = self.analyze_file(
                directory, max_single_file_bytes=max_single_file_bytes
            )
            try:
                f_size = directory.stat().st_size
            except OSError:
                f_size = 0
            return {
                'issues': issues,
                'metrics': metrics,
                'tasks': tasks,
                'analyzed_files': [str(directory)],
                'summary': self._generate_summary(issues, metrics, tasks),
                'budget': {
                    'max_files': max_files,
                    'max_bytes': max_bytes,
                    'files': 1,
                    'bytes': f_size,
                    'truncated': False,
                },
            }

        if patterns is None:
            patterns = ['*.yaml', '*.yml', '*.json', '*.toon.yaml', '*.toon.yml']

        all_issues = []
        all_metrics = []
        all_tasks = []
        analyzed_files = []
        analyzed_bytes = 0
        truncated = False
        seen: set[Path] = set()

        for root, dirs, files in os.walk(directory):
            # Prune excluded directories in-place before traversing into them
            dirs[:] = [
                d for d in dirs
                if d not in self.EXCLUDED_DIRS
                and not d.endswith(self.EXCLUDED_DIR_SUFFIXES)
            ]
            dirs.sort()
            for file_name in sorted(files):
                # Skip hidden files and self-analysis outputs
                if file_name.startswith('.'):
                    continue
                if 'analysis_summary.json' in file_name or 'local-strategy.yaml' in file_name:
                    continue

                rel_path = os.path.relpath(os.path.join(root, file_name), directory)
                if not any(fnmatch(file_name, pat) or fnmatch(rel_path, pat) for pat in patterns):
                    continue

                file_path = Path(root, file_name).resolve()
                if file_path in seen:
                    continue
                seen.add(file_path)

                if self.is_excluded(file_path, directory):
                    continue

                try:
                    file_size = file_path.stat().st_size
                except OSError:
                    file_size = 0

                if max_files is not None and len(analyzed_files) >= max_files:
                    truncated = True
                    break
                if max_bytes is not None and analyzed_bytes + file_size > max_bytes:
                    truncated = True
                    break

                if max_single_file_bytes is not None and file_size > max_single_file_bytes:
                    all_issues.append(
                        ExtractedIssue(
                            name=f"File exceeds analysis size limit in {file_path.name}",
                            description=(
                                f"File {file_path.name} exceeds maximum single file analysis size "
                                f"of {max_single_file_bytes} bytes ({file_size} bytes) and was skipped."
                            ),
                            priority="medium",
                            category="health",
                            file_path=str(file_path),
                            tags=["oversized", "skipped"],
                        )
                    )
                    continue

                issues, metrics, tasks = self.analyze_file(
                    file_path, max_single_file_bytes=max_single_file_bytes
                )

                all_issues.extend(issues)
                all_metrics.extend(metrics)
                all_tasks.extend(tasks)
                analyzed_files.append(str(file_path))
                analyzed_bytes += file_size
            if truncated:
                break

        return {
            'issues': all_issues,
            'metrics': all_metrics,
            'tasks': all_tasks,
            'analyzed_files': analyzed_files,
            'summary': self._generate_summary(all_issues, all_metrics, all_tasks),
            'budget': {
                'max_files': max_files,
                'max_bytes': max_bytes,
                'files': len(analyzed_files),
                'bytes': analyzed_bytes,
                'truncated': truncated,
            },
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
