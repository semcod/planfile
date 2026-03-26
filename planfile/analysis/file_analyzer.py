"""
File analysis module for planfile generation.
Extracts issues, metrics, and tasks from various file formats.
"""

import os
import re
import json
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Tuple
from dataclasses import dataclass, asdict

from .models import ExtractedIssue, ExtractedMetric, ExtractedTask


class FileAnalyzer:
    """Analyzes YAML/JSON files to extract issues and metrics."""
    
    def __init__(self):
        self.extractors = {
            '.yaml': self._analyze_yaml,
            '.yml': self._analyze_yaml,
            '.json': self._analyze_json,
            '.toon.yaml': self._analyze_toon,
            '.toon.yml': self._analyze_toon,
        }
        
        # Pattern matchers for common issue formats
        self.issue_patterns = {
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
        self.metric_patterns = {
            'coverage': re.compile(r'coverage[:\s=]+(\d+\.?\d*)%?', re.IGNORECASE),
            'cc': re.compile(r'CC[=_]?(\d+\.?\d*)', re.IGNORECASE),
            'complexity': re.compile(r'complexity[:\s=]+(\d+\.?\d*)', re.IGNORECASE),
            'errors': re.compile(r'errors?[:\s=]+(\d+)', re.IGNORECASE),
            'warnings': re.compile(r'warnings?[:\s=]+(\d+)', re.IGNORECASE),
            'tests': re.compile(r'tests?[:\s=]+(\d+)', re.IGNORECASE),
            'performance': re.compile(r'(\d+\.?\d*)\s*(ms|sec|s)', re.IGNORECASE),
        }
    
    def analyze_file(self, file_path: Path) -> Tuple[List[ExtractedIssue], List[ExtractedMetric], List[ExtractedTask]]:
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
            issues, metrics, tasks = self._analyze_text(file_path)
        else:
            issues, metrics, tasks = analyzer(file_path)
        
        return issues, metrics, tasks
    
    def _analyze_toon(self, file_path: Path) -> Tuple[List[ExtractedIssue], List[ExtractedMetric], List[ExtractedTask]]:
        """Analyze Toon format files with enhanced parsing."""
        issues = []
        metrics = []
        tasks = []
        
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            # Parse as text first to extract header info
            lines = content.split('\n')
            
            # Extract from header line (first non-comment line)
            for line in lines[:5]:
                if line.strip() and not line.startswith('#'):
                    # Parse metrics from header
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
                            
                            # Create issue if CC is high
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
            
            # Parse structured sections
            current_section = None
            for i, line in enumerate(lines):
                line = line.strip()
                
                # Detect section headers
                if line.startswith('HEALTH['):
                    current_section = 'health'
                elif line.startswith('REFACTOR['):
                    current_section = 'refactor'
                elif line.startswith('WARNINGS['):
                    current_section = 'warnings'
                elif line.startswith('ERRORS['):
                    current_section = 'errors'
                elif line.startswith('SUMMARY:'):
                    current_section = 'summary'
                elif line.startswith('DUPLICATES['):
                    current_section = 'duplicates'
                elif line and not line.startswith('#') and ':' not in line and current_section:
                    current_section = None
                
                # Process based on section
                if current_section == 'health' and 'CC=' in line and 'limit:' in line:
                    # Extract high-CC function
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
                            line_number=i+1,
                            effort_estimate=f"{max(2, cc_value // 5)}h",
                            tags=["complexity", "refactor"]
                        ))
                
                elif current_section == 'summary':
                    # Extract summary metrics
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
            
            # Also do general text analysis for TODOs etc.
            text_issues, text_metrics, text_tasks = self._analyze_text(file_path)
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
    
    def _analyze_yaml(self, file_path: Path) -> Tuple[List[ExtractedIssue], List[ExtractedMetric], List[ExtractedTask]]:
        """Analyze YAML file with better error handling."""
        issues = []
        metrics = []
        tasks = []
        
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            # Try to parse as YAML
            try:
                data = yaml.safe_load(content)
                
                # Extract from structure
                issues.extend(self._extract_from_yaml_structure(data, str(file_path)))
                
            except yaml.YAMLError as e:
                # If it's a toon file, use the toon analyzer
                if 'toon' in str(file_path):
                    return self._analyze_toon(file_path)
                
                # Otherwise create an issue for the parsing error
                issues.append(ExtractedIssue(
                    title=f"Fix YAML syntax in {file_path.name}",
                    description=f"YAML parsing error: {str(e)}",
                    priority="high",
                    category="bug",
                    file_path=str(file_path),
                    effort_estimate="1h",
                    tags=["yaml", "syntax"]
                ))
            
            # Extract from comments and text
            text_issues, text_metrics, text_tasks = self._analyze_text(file_path)
            issues.extend(text_issues)
            metrics.extend(text_metrics)
            tasks.extend(text_tasks)
            
        except Exception as e:
            issues.append(ExtractedIssue(
                title=f"Failed to parse {file_path.name}",
                description=f"File error: {str(e)}",
                priority="high",
                category="bug",
                file_path=str(file_path)
            ))
        
        return issues, metrics, tasks
    
    def _analyze_json(self, file_path: Path) -> Tuple[List[ExtractedIssue], List[ExtractedMetric], List[ExtractedTask]]:
        """Analyze JSON file."""
        issues = []
        metrics = []
        tasks = []
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Extract from structure
            issues.extend(self._extract_from_json_structure(data, str(file_path)))
            
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
    
    def _analyze_text(self, file_path: Path) -> Tuple[List[ExtractedIssue], List[ExtractedMetric], List[ExtractedTask]]:
        """Analyze text content for TODOs, FIXMEs, and metrics."""
        issues = []
        metrics = []
        tasks = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
            
            # Extract issues from patterns
            for pattern_name, pattern in self.issue_patterns.items():
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
            for metric_name, pattern in self.metric_patterns.items():
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
    
    def _extract_from_yaml_structure(self, data: Any, path: str, parent_key: str = "") -> List[ExtractedIssue]:
        """Extract issues from YAML structure."""
        issues = []
        
        if isinstance(data, dict):
            for key, value in data.items():
                full_key = f"{parent_key}.{key}" if parent_key else key
                
                # Look for common issue indicators
                if isinstance(value, str):
                    if any(keyword in value.lower() for keyword in ['error', 'fail', 'bug', 'issue']):
                        issues.append(ExtractedIssue(
                            title=f"Issue in {full_key}",
                            description=value,
                            priority="medium",
                            category="bug",
                            file_path=path
                        ))
                
                # Recurse
                issues.extend(self._extract_from_yaml_structure(value, path, full_key))
        
        elif isinstance(data, list):
            for i, item in enumerate(data):
                issues.extend(self._extract_from_yaml_structure(item, path, f"{parent_key}[{i}]"))
        
        return issues
    
    def _extract_from_json_structure(self, data: Any, path: str, parent_key: str = "") -> List[ExtractedIssue]:
        """Extract issues from JSON structure."""
        # Similar to YAML extraction
        return self._extract_from_yaml_structure(data, path, parent_key)
    
    def analyze_directory(self, directory: Path, patterns: List[str] = None) -> Dict[str, Any]:
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
                if file_path.name.startswith('.') or any(skip in str(file_path) for skip in ['__pycache__', '.git', 'node_modules', '.pytest_cache']):
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
    
    def _generate_summary(self, issues: List[ExtractedIssue], metrics: List[ExtractedMetric], tasks: List[ExtractedTask]) -> Dict[str, Any]:
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
