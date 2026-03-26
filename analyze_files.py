#!/usr/bin/env python3
"""
YAML/JSON File Analyzer for Ticket and Sprint Generation
Extracts key information from various file formats to generate project tasks.
"""

import os
import sys
import json
import yaml
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import re


@dataclass
class ExtractedIssue:
    """Represents an issue extracted from a file."""
    title: str
    description: str
    priority: str  # critical, high, medium, low
    category: str  # bug, feature, refactor, test, docs, etc.
    file_path: str
    line_number: Optional[int] = None
    effort_estimate: Optional[str] = None
    tags: List[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []


@dataclass
class ExtractedMetric:
    """Represents a metric extracted from a file."""
    name: str
    value: Union[float, int, str]
    threshold: Optional[Union[float, int, str]] = None
    status: Optional[str] = None  # good, warning, critical
    file_path: str = None


@dataclass
class ExtractedTask:
    """Represents a task extracted from a file."""
    name: str
    description: str
    type: str  # development, testing, review, documentation
    dependencies: List[str] = None
    acceptance_criteria: List[str] = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []
        if self.acceptance_criteria is None:
            self.acceptance_criteria = []


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
    
    def _analyze_yaml(self, file_path: Path) -> Tuple[List[ExtractedIssue], List[ExtractedMetric], List[ExtractedTask]]:
        """Analyze YAML file."""
        issues = []
        metrics = []
        tasks = []
        
        try:
            with open(file_path, 'r') as f:
                content = f.read()
                data = yaml.safe_load(content)
            
            # Extract from structure
            issues.extend(self._extract_from_yaml_structure(data, str(file_path)))
            
            # Extract from comments and text
            text_issues, text_metrics, text_tasks = self._analyze_text(file_path)
            issues.extend(text_issues)
            metrics.extend(text_metrics)
            tasks.extend(text_tasks)
            
        except Exception as e:
            issues.append(ExtractedIssue(
                title=f"Failed to parse {file_path.name}",
                description=f"YAML parsing error: {str(e)}",
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
                title=f"Failed to parse {file_path.name}",
                description=f"JSON parsing error: {str(e)}",
                priority="high",
                category="bug",
                file_path=str(file_path)
            ))
        
        return issues, metrics, tasks
    
    def _analyze_toon(self, file_path: Path) -> Tuple[List[ExtractedIssue], List[ExtractedMetric], List[ExtractedTask]]:
        """Analyze Toon format files (from code2llm/vallm/redup)."""
        issues = []
        metrics = []
        tasks = []
        
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            # Parse header for metrics
            lines = content.split('\n')
            for line in lines[:10]:  # Check first 10 lines for header
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
                
                if 'critical:' in line:
                    critical_match = re.search(r'critical:(\d+)', line)
                    if critical_match:
                        metrics.append(ExtractedMetric(
                            name="Critical Functions",
                            value=int(critical_match.group(1)),
                            threshold=0,
                            status="critical" if int(critical_match.group(1)) > 0 else "good",
                            file_path=str(file_path)
                        ))
                
                if 'errors:' in line:
                    error_match = re.search(r'errors:\s*(\d+)', line)
                    if error_match:
                        error_count = int(error_match.group(1))
                        metrics.append(ExtractedMetric(
                            name="Validation Errors",
                            value=error_count,
                            threshold=0,
                            status="critical" if error_count > 0 else "good",
                            file_path=str(file_path)
                        ))
                        
                        if error_count > 0:
                            issues.append(ExtractedIssue(
                                title=f"Fix {error_count} validation errors",
                                description=f"Validation errors found in {file_path.name}",
                                priority="critical",
                                category="bug",
                                file_path=str(file_path),
                                effort_estimate=f"{max(1, error_count // 5)}d"
                            ))
                
                if 'warnings:' in line:
                    warning_match = re.search(r'warnings:\s*(\d+)', line)
                    if warning_match:
                        warning_count = int(warning_match.group(1))
                        metrics.append(ExtractedMetric(
                            name="Validation Warnings",
                            value=warning_count,
                            threshold=0,
                            status="warning" if warning_count > 0 else "good",
                            file_path=str(file_path)
                        ))
                        
                        if warning_count > 0:
                            issues.append(ExtractedIssue(
                                title=f"Address {warning_count} validation warnings",
                                description=f"Validation warnings in {file_path.name}",
                                priority="medium",
                                category="refactor",
                                file_path=str(file_path),
                                effort_estimate=f"{max(1, warning_count // 3)}d"
                            ))
            
            # Extract high-CC functions
            in_health = False
            for line in lines:
                if 'HEALTH[' in line:
                    in_health = True
                elif 'REFACTOR[' in line:
                    in_health = False
                elif in_health and 'CC=' in line and 'limit:15' in line:
                    func_match = re.search(r'(\w+)\s+CC=(\d+)', line)
                    if func_match:
                        func_name = func_match.group(1)
                        cc_value = int(func_match.group(2))
                        issues.append(ExtractedIssue(
                            title=f"Refactor {func_name} (CC={cc_value})",
                            description=f"Function has high cyclomatic complexity",
                            priority="high" if cc_value > 20 else "medium",
                            category="refactor",
                            file_path=str(file_path),
                            effort_estimate=f"{cc_value // 5}h",
                            tags=["complexity", "refactor"]
                        ))
            
            # Extract duplication info
            if 'duplication' in str(file_path).lower():
                dup_match = re.search(r'dup_groups:\s*(\d+)', content)
                if dup_match and int(dup_match.group(1)) > 0:
                    dup_count = int(dup_match.group(1))
                    issues.append(ExtractedIssue(
                        title=f"Remove {dup_count} code duplication groups",
                        description="Extract duplicated code into reusable functions",
                        priority="medium",
                        category="refactor",
                        file_path=str(file_path),
                        effort_estimate=f"{dup_count * 2}h",
                        tags=["duplication", "cleanup"]
                    ))
            
        except Exception as e:
            issues.append(ExtractedIssue(
                title=f"Failed to analyze {file_path.name}",
                description=f"Analysis error: {str(e)}",
                priority="medium",
                category="bug",
                file_path=str(file_path)
            ))
        
        return issues, metrics, tasks
    
    def _analyze_text(self, file_path: Path) -> Tuple[List[ExtractedIssue], List[ExtractedMetric], List[ExtractedTask]]:
        """Analyze text content for TODOs, FIXMEs, and metrics."""
        issues = []
        metrics = []
        tasks = []
        
        try:
            with open(file_path, 'r') as f:
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
                    elif metric_name == 'cc':
                        value = float(value)
                        metrics.append(ExtractedMetric(
                            name="Cyclomatic Complexity",
                            value=value,
                            threshold=10.0,
                            status="warning" if value > 10 else "good",
                            file_path=str(file_path)
                        ))
            
        except Exception as e:
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
                if file_path.name.startswith('.') or any(skip in str(file_path) for skip in ['__pycache__', '.git', 'node_modules']):
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


class SprintGenerator:
    """Generates sprints and tickets from extracted information."""
    
    def __init__(self):
        self.sprint_templates = {
            'critical': {
                'name': 'Critical Issues Sprint',
                'duration': '1 week',
                'focus': 'Fix critical bugs and issues'
            },
            'quality': {
                'name': 'Quality Improvement Sprint',
                'duration': '2 weeks',
                'focus': 'Improve code quality and test coverage'
            },
            'feature': {
                'name': 'Feature Development Sprint',
                'duration': '2 weeks',
                'focus': 'Implement new features'
            },
            'optimization': {
                'name': 'Performance Optimization Sprint',
                'duration': '1 week',
                'focus': 'Optimize performance and reduce complexity'
            }
        }
    
    def generate_sprints(self, analysis_result: Dict[str, Any], max_sprints: int = 4) -> List[Dict[str, Any]]:
        """Generate sprints based on analysis results."""
        issues = analysis_result['issues']
        metrics = analysis_result['metrics']
        
        # Group issues by priority
        critical_issues = [i for i in issues if i.priority == 'critical']
        high_issues = [i for i in issues if i.priority == 'high']
        medium_issues = [i for i in issues if i.priority == 'medium']
        low_issues = [i for i in issues if i.priority == 'low']
        
        sprints = []
        sprint_id = 1
        
        # Sprint 1: Critical Issues
        if critical_issues and sprint_id <= max_sprints:
            sprint = self._create_sprint(
                f"sprint-{sprint_id}",
                "Critical Issues Resolution",
                "1 week",
                ["Fix all critical bugs and errors"],
                critical_issues[:10]  # Limit to 10 issues
            )
            sprints.append(sprint)
            sprint_id += 1
        
        # Sprint 2: High Priority & Quality
        high_and_quality = high_issues + [i for i in medium_issues if i.category in ['refactor', 'test']]
        if high_and_quality and sprint_id <= max_sprints:
            sprint = self._create_sprint(
                f"sprint-{sprint_id}",
                "Quality & High Priority",
                "2 weeks",
                ["Address high priority issues", "Improve code quality"],
                high_and_quality[:15]
            )
            sprints.append(sprint)
            sprint_id += 1
        
        # Sprint 3: Medium Priority
        remaining_medium = [i for i in medium_issues if i not in high_and_quality]
        if remaining_medium and sprint_id <= max_sprints:
            sprint = self._create_sprint(
                f"sprint-{sprint_id}",
                "Feature Development",
                "2 weeks",
                ["Implement features and improvements"],
                remaining_medium[:15]
            )
            sprints.append(sprint)
            sprint_id += 1
        
        # Sprint 4: Low Priority & Polish
        if low_issues and sprint_id <= max_sprints:
            sprint = self._create_sprint(
                f"sprint-{sprint_id}",
                "Polish & Documentation",
                "1 week",
                ["Documentation", "Minor improvements"],
                low_issues[:10]
            )
            sprints.append(sprint)
        
        return sprints
    
    def _create_sprint(self, sprint_id: str, name: str, duration: str, objectives: List[str], issues: List[ExtractedIssue]) -> Dict[str, Any]:
        """Create a sprint from issues."""
        # Group issues by category for task patterns
        category_groups = {}
        for issue in issues:
            if issue.category not in category_groups:
                category_groups[issue.category] = []
            category_groups[issue.category].append(issue)
        
        task_patterns = []
        for category, category_issues in category_groups.items():
            task_patterns.append({
                'name': f"Resolve {category.title()} Issues",
                'description': f"Fix {len(category_issues)} {category} issues",
                'task_type': self._map_category_to_task_type(category),
                'priority': self._get_highest_priority(category_issues),
                'estimate': self._estimate_effort(category_issues),
                'issues': [asdict(issue) for issue in category_issues]
            })
        
        return {
            'id': sprint_id,
            'name': name,
            'duration': duration,
            'objectives': objectives,
            'task_patterns': task_patterns,
            'issue_count': len(issues)
        }
    
    def _map_category_to_task_type(self, category: str) -> str:
        """Map issue category to task type."""
        mapping = {
            'bug': 'bugfix',
            'refactor': 'refactor',
            'feature': 'feature',
            'test': 'test',
            'documentation': 'documentation',
            'performance': 'optimize',
            'technical_debt': 'refactor',
            'security': 'security'
        }
        return mapping.get(category, 'task')
    
    def _get_highest_priority(self, issues: List[ExtractedIssue]) -> str:
        """Get highest priority from issues."""
        priority_order = {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}
        highest = max(issues, key=lambda x: priority_order.get(x.priority, 0))
        return highest.priority
    
    def _estimate_effort(self, issues: List[ExtractedIssue]) -> str:
        """Estimate total effort for issues."""
        total_hours = 0
        for issue in issues:
            if issue.effort_estimate:
                # Parse existing estimate
                if 'h' in issue.effort_estimate:
                    total_hours += int(issue.effort_estimate.replace('h', ''))
                elif 'd' in issue.effort_estimate:
                    total_hours += int(issue.effort_estimate.replace('d', '')) * 8
            else:
                # Default estimate based on priority
                priority_hours = {'critical': 8, 'high': 6, 'medium': 4, 'low': 2}
                total_hours += priority_hours.get(issue.priority, 4)
        
        # Convert to days
        days = total_hours / 8
        if days < 1:
            return f"{total_hours}h"
        else:
            return f"{int(days)}d"
    
    def generate_tickets(self, analysis_result: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """Generate tickets from issues."""
        issues = analysis_result['issues']
        
        tickets = {
            'critical': [],
            'high': [],
            'medium': [],
            'low': []
        }
        
        for issue in issues:
            ticket = {
                'title': issue.title,
                'description': issue.description,
                'priority': issue.priority,
                'category': issue.category,
                'file_path': issue.file_path,
                'line_number': issue.line_number,
                'effort_estimate': issue.effort_estimate,
                'tags': issue.tags
            }
            
            tickets[issue.priority].append(ticket)
        
        return tickets


def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(
        description="Analyze YAML/JSON files and generate sprints/tickets"
    )
    
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Path to analyze (default: current directory)"
    )
    
    parser.add_argument(
        "--patterns",
        nargs="+",
        default=["*.yaml", "*.yml", "*.json", "*.toon.yaml", "*.toon.yml"],
        help="File patterns to analyze"
    )
    
    parser.add_argument(
        "--output",
        default="generated-planfile.yaml",
        help="Output file for generated planfile"
    )
    
    parser.add_argument(
        "--format",
        choices=["yaml", "json"],
        default="yaml",
        help="Output format"
    )
    
    parser.add_argument(
        "--max-sprints",
        type=int,
        default=4,
        help="Maximum number of sprints to generate"
    )
    
    args = parser.parse_args()
    
    # Initialize analyzers
    analyzer = FileAnalyzer()
    generator = SprintGenerator()
    
    # Analyze directory
    print(f"🔍 Analyzing {args.path}...")
    analysis_result = analyzer.analyze_directory(Path(args.path), args.patterns)
    
    # Print summary
    summary = analysis_result['summary']
    print(f"\n📊 Analysis Summary:")
    print(f"  Files analyzed: {len(analysis_result['analyzed_files'])}")
    print(f"  Issues found: {summary['total_issues']}")
    print(f"  - Critical: {summary['priority_breakdown']['critical']}")
    print(f"  - High: {summary['priority_breakdown']['high']}")
    print(f"  - Medium: {summary['priority_breakdown']['medium']}")
    print(f"  - Low: {summary['priority_breakdown']['low']}")
    print(f"  Metrics: {summary['total_metrics']}")
    print(f"  Critical metrics: {summary['critical_metrics']}")
    
    # Generate sprints
    print(f"\n🏃 Generating sprints...")
    sprints = generator.generate_sprints(analysis_result, args.max_sprints)
    print(f"  Generated {len(sprints)} sprints")
    
    # Generate tickets
    print(f"🎫 Generating tickets...")
    tickets = generator.generate_tickets(analysis_result)
    total_tickets = sum(len(t) for t in tickets.values())
    print(f"  Generated {total_tickets} tickets")
    
    # Create planfile structure
    planfile = {
        'name': 'Generated from File Analysis',
        'project_name': Path(args.path).name,
        'project_type': 'improvement',
        'domain': 'software',
        'goal': 'Address issues found in file analysis',
        'sprints': sprints,
        'tickets': tickets,
        'metrics': {
            'current': {
                'total_issues': summary['total_issues'],
                'critical_issues': summary['priority_breakdown']['critical'],
                'high_issues': summary['priority_breakdown']['high'],
                'medium_issues': summary['priority_breakdown']['medium'],
                'low_issues': summary['priority_breakdown']['low']
            }
        },
        'analysis_summary': {
            'analyzed_files': analysis_result['analyzed_files'],
            'total_metrics': summary['total_metrics'],
            'critical_metrics': summary['critical_metrics']
        }
    }
    
    # Save output
    output_path = Path(args.output)
    print(f"\n💾 Saving to {output_path}...")
    
    if args.format == 'json':
        with open(output_path, 'w') as f:
            json.dump(planfile, f, indent=2, default=str)
    else:
        with open(output_path, 'w') as f:
            yaml.dump(planfile, f, default_flow_style=False, sort_keys=False)
    
    print(f"✅ Done! Generated planfile saved to {output_path}")
    
    # Show sample tickets
    if tickets['critical']:
        print(f"\n🚨 Critical Tickets Sample:")
        for ticket in tickets['critical'][:3]:
            print(f"  - {ticket['title']} ({ticket['file_path']})")


if __name__ == "__main__":
    main()
