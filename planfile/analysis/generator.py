"""
Main planfile generator from code analysis.
Integrates file analysis and sprint generation to create complete strategies.
"""

import os
import sys
import json
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

from .file_analyzer import FileAnalyzer
from .sprint_generator import SprintGenerator
from .external_tools import ExternalToolRunner, AnalysisResults
from ..models import Strategy


class PlanfileGenerator:
    """Generate comprehensive planfile from file analysis."""
    
    def __init__(self):
        self.analyzer = FileAnalyzer()
        self.generator = SprintGenerator()
        self.external_runner: Optional[ExternalToolRunner] = None
    
    def generate_with_external_tools(self,
                                     project_path: str = ".",
                                     project_name: str = None,
                                     max_sprints: int = 4,
                                     focus_area: str = None) -> Strategy:
        """Generate planfile using external analysis tools (code2llm, vallm, redup).
        
        This method runs external tools if available and incorporates their
        results into the generated strategy.
        
        Args:
            project_path: Path to project directory
            project_name: Name of the project (defaults to directory name)
            max_sprints: Maximum number of sprints to generate
            focus_area: Specific focus area (quality, security, performance, etc.)
        
        Returns:
            Strategy object with external tool analysis incorporated
        """
        print("=" * 60)
        print("GENERATING PLANFILE WITH EXTERNAL TOOLS")
        print("=" * 60)
        
        # Run external tools
        self.external_runner = ExternalToolRunner(Path(project_path))
        external_results = self.external_runner.run_all()
        
        # Convert external results to internal format
        analysis_result = self._external_to_internal_analysis(external_results)
        
        # Generate strategy from combined analysis
        return self.generate_from_analysis(
            analysis_path=str(self.external_runner.output_dir),
            project_name=project_name,
            max_sprints=max_sprints,
            focus_area=focus_area,
            external_metrics=self._extract_external_metrics(external_results)
        )
    
    def _external_to_internal_analysis(self, results: AnalysisResults) -> Dict[str, Any]:
        """Convert external tool results to internal analysis format."""
        issues = []
        metrics = []
        
        # Create issues from high CC functions
        for func in results.high_cc_functions:
            issues.append({
                'title': f"Refactor {func['name']} (CC={func['cc']})",
                'description': f"Function has high cyclomatic complexity",
                'priority': 'critical' if func['cc'] > 20 else 'high',
                'category': 'refactor',
                'effort_estimate': f"{max(2, func['cc'] // 5)}h",
                'file_path': 'analysis.toon.yaml'
            })
        
        # Create issues from validation errors
        if results.validation_errors > 0:
            issues.append({
                'title': f"Fix {results.validation_errors} validation errors",
                'description': "Resolve all validation errors found in project",
                'priority': 'critical',
                'category': 'bug',
                'effort_estimate': f"{max(1, results.validation_errors // 5)}d",
                'file_path': 'validation.toon.yaml'
            })
        
        # Create issues from validation warnings
        if results.validation_warnings > 0:
            issues.append({
                'title': f"Address {results.validation_warnings} validation warnings",
                'description': "Fix all validation warnings",
                'priority': 'medium',
                'category': 'refactor',
                'effort_estimate': f"{max(1, results.validation_warnings // 3)}d",
                'file_path': 'validation.toon.yaml'
            })
        
        # Create issues from duplication
        if results.duplication_groups > 0:
            issues.append({
                'title': f"Remove {results.duplication_groups} code duplication groups",
                'description': "Extract duplicated code into reusable functions",
                'priority': 'medium',
                'category': 'refactor',
                'effort_estimate': f"{results.duplication_groups * 2}h",
                'file_path': 'duplication.toon.yaml'
            })
        
        return {
            'issues': issues,
            'metrics': metrics,
            'summary': {
                'total_issues': len(issues),
                'priority_breakdown': {
                    'critical': len([i for i in issues if i['priority'] == 'critical']),
                    'high': len([i for i in issues if i['priority'] == 'high']),
                    'medium': len([i for i in issues if i['priority'] == 'medium']),
                    'low': len([i for i in issues if i['priority'] == 'low']),
                },
                'category_breakdown': {},
                'total_metrics': len(metrics),
                'critical_metrics': 0,
                'total_tasks': 0
            }
        }
    
    def _extract_external_metrics(self, results: AnalysisResults) -> Dict[str, Any]:
        """Extract metrics from external tool results."""
        return {
            'average_cc': results.cc_average,
            'critical_functions': results.critical_functions,
            'high_cc_functions': results.high_cc_functions,
            'validation_errors': results.validation_errors,
            'validation_warnings': results.validation_warnings,
            'duplication_groups': results.duplication_groups,
            'saved_lines': results.saved_lines,
            'pass_rate': results.pass_rate
        }
    
    def generate_from_analysis(self, 
                             analysis_path: str,
                             project_name: str = None,
                             max_sprints: int = 4,
                             focus_area: str = None,
                             external_metrics: Optional[Dict[str, Any]] = None) -> Strategy:
        """Generate planfile from analyzed files.
        
        Args:
            analysis_path: Path to analysis results directory
            project_name: Name of the project (defaults to directory name)
            max_sprints: Maximum number of sprints to generate
            focus_area: Specific focus area (quality, security, performance, etc.)
            external_metrics: Optional metrics from external tools
        
        Returns:
            Strategy object ready for validation and application
        """
        
        # Analyze files
        analysis_result = self.analyzer.analyze_directory(Path(analysis_path))
        
        # Get summary
        summary = analysis_result['summary']
        
        # Generate sprints
        sprints = self.generator.generate_sprints(analysis_result, max_sprints)
        
        # Generate tickets
        tickets = self.generator.generate_tickets(analysis_result)
        
        # Extract key metrics for quality gates
        metrics = self._extract_key_metrics(analysis_result, external_metrics)
        
        # Create strategy
        project_name = project_name or Path(analysis_path).name
        
        strategy_data = {
            'name': f'{project_name.title()} Improvement Plan',
            'project_name': project_name,
            'project_type': 'improvement',
            'domain': 'software',
            'goal': self._generate_goal(summary, metrics, focus_area),
            
            'goals': self._generate_goals(summary, metrics, focus_area),
            
            'quality_gates': self._generate_quality_gates(metrics),
            
            'sprints': sprints,
            
            'tasks': self._generate_tasks(analysis_result),
            
            'metrics': {
                'current': metrics,
                'target': self._generate_target_metrics(metrics)
            },
            
            'tickets': tickets,
            
            'risks': self._generate_risks(analysis_result),
            
            'success_criteria': self._generate_success_criteria(metrics)
        }
        
        # Convert to Strategy object
        return self._create_strategy_object(strategy_data)
    
    def generate_from_current_project(self,
                                    project_path: str = ".",
                                    patterns: List[str] = None,
                                    **kwargs) -> Strategy:
        """Generate planfile by analyzing current project files.
        
        Args:
            project_path: Path to project directory
            patterns: File patterns to analyze
            **kwargs: Additional arguments for generate_from_analysis
        
        Returns:
            Strategy object
        """
        if patterns is None:
            patterns = ['*.yaml', '*.yml', '*.json', '*.toon.yaml', '*.toon.yml', '*.py']
        
        # Analyze the project directly
        analysis_result = self.analyzer.analyze_directory(Path(project_path), patterns)
        
        # Save analysis results temporarily for reference
        temp_dir = Path(project_path) / ".planfile_analysis"
        temp_dir.mkdir(exist_ok=True)
        
        with open(temp_dir / "analysis_summary.json", 'w') as f:
            # Convert dataclasses to dicts for JSON serialization
            serializable_result = self._make_serializable(analysis_result)
            json.dump(serializable_result, f, indent=2, default=str)
        
        # Generate strategy from analysis
        return self.generate_from_analysis(
            analysis_path=str(temp_dir),
            **kwargs
        )
    
    def _extract_key_metrics(self, analysis_result: Dict[str, Any], external_metrics: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Extract key metrics from analysis."""
        metrics = {}
        
        # Use external metrics if available
        if external_metrics:
            metrics.update(external_metrics)
        
        # Extract CC metrics from file analysis
        cc_metrics = [m for m in analysis_result['metrics'] if 'CC' in m.name or 'complexity' in m.name.lower()]
        if cc_metrics:
            avg_cc = sum(m.value for m in cc_metrics if isinstance(m.value, (int, float))) / len(cc_metrics)
            metrics['average_cc'] = round(avg_cc, 1)
        
        # Extract critical functions
        critical_funcs = [m for m in analysis_result['metrics'] if 'critical' in m.name.lower() and 'function' in m.name.lower()]
        if critical_funcs:
            metrics['critical_functions'] = sum(m.value for m in critical_funcs if isinstance(m.value, int))
        
        # Extract validation metrics
        errors = [m for m in analysis_result['metrics'] if 'error' in m.name.lower()]
        warnings = [m for m in analysis_result['metrics'] if 'warning' in m.name.lower()]
        
        metrics['validation_errors'] = sum(m.value for m in errors if isinstance(m.value, int))
        metrics['validation_warnings'] = sum(m.value for m in warnings if isinstance(m.value, int))
        
        # Extract duplication
        dup_metrics = [m for m in analysis_result['metrics'] if 'duplication' in m.name.lower()]
        if dup_metrics:
            metrics['duplication_groups'] = sum(m.value for m in dup_metrics if isinstance(m.value, int))
        
        # Extract test coverage if available
        coverage = [m for m in analysis_result['metrics'] if 'coverage' in m.name.lower()]
        if coverage:
            metrics['test_coverage'] = coverage[0].value
        
        return metrics
    
    def _generate_goal(self, summary: Dict[str, Any], metrics: Dict[str, Any], focus_area: Optional[str]) -> str:
        """Generate main goal based on analysis."""
        if focus_area:
            focus_goals = {
                'quality': 'Improve overall code quality and maintainability',
                'security': 'Enhance security posture and address vulnerabilities',
                'performance': 'Optimize performance and reduce bottlenecks',
                'testing': 'Improve test coverage and test quality',
                'documentation': 'Complete and improve project documentation'
            }
            return focus_goals.get(focus_area, 'Systematically address issues found in analysis')
        
        # Default goal based on critical issues
        if summary['priority_breakdown']['critical'] > 0:
            return f"Address {summary['priority_breakdown']['critical']} critical issues and improve code quality"
        elif metrics.get('average_cc', 0) > 4:
            return "Reduce code complexity and improve maintainability"
        else:
            return "Systematically address issues found in code analysis"
    
    def _generate_goals(self, summary: Dict[str, Any], metrics: Dict[str, Any], focus_area: Optional[str]) -> List[str]:
        """Generate goals based on analysis."""
        goals = []
        
        if summary['priority_breakdown']['critical'] > 0:
            goals.append(f"Fix all {summary['priority_breakdown']['critical']} critical issues")
        
        if metrics.get('average_cc', 0) > 3.5:
            goals.append(f"Reduce average cyclomatic complexity from {metrics['average_cc']} to ≤ 3.5")
        
        if metrics.get('critical_functions', 0) > 0:
            goals.append(f"Eliminate all {metrics['critical_functions']} high-complexity functions")
        
        if metrics.get('validation_errors', 0) > 0:
            goals.append(f"Resolve all {metrics['validation_errors']} validation errors")
        
        if metrics.get('validation_warnings', 0) > 0:
            goals.append(f"Address {metrics['validation_warnings']} validation warnings")
        
        if metrics.get('duplication_groups', 0) > 0:
            goals.append(f"Remove {metrics['duplication_groups']} code duplication groups")
        
        if metrics.get('test_coverage'):
            current = metrics['test_coverage']
            if current < 80:
                goals.append(f"Increase test coverage from {current}% to 80%")
        
        # Add focus-specific goals
        if focus_area == 'security':
            goals.append("Implement security best practices")
            goals.append("Address all security vulnerabilities")
        elif focus_area == 'performance':
            goals.append("Optimize critical performance paths")
            goals.append("Reduce resource consumption")
        elif focus_area == 'testing':
            goals.append("Achieve 80% test coverage")
            goals.append("Add integration tests")
        elif focus_area == 'documentation':
            goals.append("Document all APIs and modules")
            goals.append("Create user guides")
        
        # Add general goals
        goals.append("Improve overall code quality")
        goals.append("Ensure all files pass validation")
        
        return goals
    
    def _generate_quality_gates(self, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate quality gates based on current metrics."""
        gates = []
        
        if 'average_cc' in metrics:
            gates.append({
                'name': 'Average Cyclomatic Complexity',
                'description': 'Keep average CC below 3.5 for maintainability',
                'criteria': [f"CC̄ ≤ 3.5"],
                'required': True
            })
        
        gates.append({
            'name': 'Critical Functions',
            'description': 'No functions should have CC > 15',
            'criteria': ['All functions CC ≤ 15'],
            'required': True
        })
        
        gates.append({
            'name': 'Validation Errors',
            'description': 'All files must pass validation',
            'criteria': ['Zero validation errors'],
            'required': True
        })
        
        gates.append({
            'name': 'Validation Warnings',
            'description': 'Address all validation warnings',
            'criteria': ['Zero validation warnings'],
            'required': True
        })
        
        if 'duplication_groups' in metrics:
            gates.append({
                'name': 'Code Duplication',
                'description': 'Eliminate code duplication',
                'criteria': ['Zero duplication groups'],
                'required': True
            })
        
        gates.append({
            'name': 'Test Coverage',
            'description': 'Maintain adequate test coverage',
            'criteria': ['Coverage ≥ 80%'],
            'required': True
        })
        
        return gates
    
    def _generate_tasks(self, analysis_result: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """Generate task breakdowns."""
        tasks = {
            'critical_refactors': [],
            'standard_refactors': [],
            'bug_fixes': [],
            'test_writing': [],
            'documentation': []
        }
        
        # Group issues by category
        for issue in analysis_result['issues']:
            task = {
                'name': issue.title,
                'description': issue.description,
                'file_path': issue.file_path,
                'line_number': issue.line_number,
                'estimated_hours': self._parse_effort(issue.effort_estimate)
            }
            
            if issue.category == 'refactor':
                if issue.priority in ['critical', 'high']:
                    tasks['critical_refactors'].append(task)
                else:
                    tasks['standard_refactors'].append(task)
            elif issue.category == 'bug':
                tasks['bug_fixes'].append(task)
            elif issue.category == 'test':
                tasks['test_writing'].append(task)
            elif issue.category == 'documentation':
                tasks['documentation'].append(task)
        
        return tasks
    
    def _parse_effort(self, effort: Optional[str]) -> int:
        """Parse effort estimate to hours."""
        if not effort:
            return 4  # Default
        
        if 'h' in effort:
            return int(effort.replace('h', ''))
        elif 'd' in effort:
            return int(effort.replace('d', '')) * 8
        
        return 4
    
    def _generate_target_metrics(self, current: Dict[str, Any]) -> Dict[str, Any]:
        """Generate target metrics."""
        target = current.copy()
        
        # Set ideal targets
        target['average_cc'] = min(target.get('average_cc', 4), 3.5)
        target['critical_functions'] = 0
        target['validation_errors'] = 0
        target['validation_warnings'] = 0
        target['duplication_groups'] = 0
        target['test_coverage'] = max(target.get('test_coverage', 0), 80)
        
        return target
    
    def _generate_risks(self, analysis_result: Dict[str, Any]) -> List[Dict[str, str]]:
        """Generate risk assessment."""
        risks = []
        
        critical_count = len([i for i in analysis_result['issues'] if i.priority == 'critical'])
        
        if critical_count > 10:
            risks.append({
                'description': f"High number of critical issues ({critical_count}) may impact delivery",
                'mitigation': "Prioritize critical issues and consider additional resources"
            })
        
        if len(analysis_result['analyzed_files']) > 100:
            risks.append({
                'description': "Large codebase may require extended timeline",
                'mitigation': "Focus on high-impact files first"
            })
        
        risks.append({
            'description': "Refactoring may introduce new bugs",
            'mitigation': "Comprehensive testing and code review"
        })
        
        return risks
    
    def _generate_success_criteria(self, metrics: Dict[str, Any]) -> List[str]:
        """Generate success criteria."""
        criteria = []
        
        criteria.append("All quality gates pass")
        criteria.append("All generated tickets are completed")
        
        if 'average_cc' in metrics:
            criteria.append(f"Average CC reduced from {metrics['average_cc']} to ≤ 3.5")
        
        criteria.append("Zero validation errors")
        criteria.append("Code duplication eliminated")
        
        if 'test_coverage' in metrics:
            criteria.append(f"Test coverage increased to 80%")
        
        criteria.append("All files pass linting and validation")
        
        return criteria
    
    def _create_strategy_object(self, strategy_data: Dict[str, Any]) -> Strategy:
        """Create a Strategy object from data."""
        # This would need to be implemented based on the Strategy model
        # For now, return the data as-is
        return strategy_data
    
    def _make_serializable(self, obj: Any) -> Any:
        """Convert objects to JSON-serializable format."""
        if hasattr(obj, '__dict__'):
            return {k: self._make_serializable(v) for k, v in obj.__dict__.items()}
        elif isinstance(obj, dict):
            return {k: self._make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._make_serializable(item) for item in obj]
        elif hasattr(obj, '__name__'):  # Functions, classes, etc.
            return str(obj)
        else:
            return obj


# Create a singleton instance
generator = PlanfileGenerator()
