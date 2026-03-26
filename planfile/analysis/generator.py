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

from .generators.metrics_extractor import extract_key_metrics
from .generators.strategy_builder import (
    generate_goal,
    generate_goals,
    generate_quality_gates,
    generate_tasks,
    parse_effort,
    generate_target_metrics,
    generate_risks,
    generate_success_criteria
)

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
        """Generate planfile using external analysis tools (code2llm, vallm, redup)."""
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
        
        if results.validation_errors > 0:
            issues.append({
                'title': f"Fix {results.validation_errors} validation errors",
                'description': "Resolve all validation errors found in project",
                'priority': 'critical',
                'category': 'bug',
                'effort_estimate': f"{max(1, results.validation_errors // 5)}d",
                'file_path': 'validation.toon.yaml'
            })
        
        if results.validation_warnings > 0:
            issues.append({
                'title': f"Address {results.validation_warnings} validation warnings",
                'description': "Fix all validation warnings",
                'priority': 'medium',
                'category': 'refactor',
                'effort_estimate': f"{max(1, results.validation_warnings // 3)}d",
                'file_path': 'validation.toon.yaml'
            })
        
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
        """Generate planfile from analyzed files."""
        # Analyze files
        analysis_result = self.analyzer.analyze_directory(Path(analysis_path))
        summary = analysis_result['summary']
        sprints = self.generator.generate_sprints(analysis_result, max_sprints)
        tickets = self.generator.generate_tickets(analysis_result)
        
        metrics = self._extract_key_metrics(analysis_result, external_metrics)
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
        
        return self._create_strategy_object(strategy_data)
    
    def generate_from_current_project(self,
                                    project_path: str = ".",
                                    patterns: List[str] = None,
                                    **kwargs) -> Strategy:
        """Generate planfile by analyzing current project files."""
        if patterns is None:
            patterns = ['*.yaml', '*.yml', '*.json', '*.toon.yaml', '*.toon.yml', '*.py']
        
        analysis_result = self.analyzer.analyze_directory(Path(project_path), patterns)
        
        temp_dir = Path(project_path) / ".planfile_analysis"
        temp_dir.mkdir(exist_ok=True)
        
        with open(temp_dir / "analysis_summary.json", 'w') as f:
            serializable_result = self._make_serializable(analysis_result)
            json.dump(serializable_result, f, indent=2, default=str)
        
        return self.generate_from_analysis(
            analysis_path=str(temp_dir),
            **kwargs
        )
    
    def _extract_key_metrics(self, analysis_result: Dict[str, Any], external_metrics: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return extract_key_metrics(analysis_result, external_metrics)
    
    def _generate_goal(self, summary: Dict[str, Any], metrics: Dict[str, Any], focus_area: Optional[str]) -> str:
        return generate_goal(summary, metrics, focus_area)
    
    def _generate_goals(self, summary: Dict[str, Any], metrics: Dict[str, Any], focus_area: Optional[str]) -> List[str]:
        return generate_goals(summary, metrics, focus_area)
    
    def _generate_quality_gates(self, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        return generate_quality_gates(metrics)
    
    def _generate_tasks(self, analysis_result: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        return generate_tasks(analysis_result)
    
    def _parse_effort(self, effort: Optional[str]) -> int:
        return parse_effort(effort)
    
    def _generate_target_metrics(self, current: Dict[str, Any]) -> Dict[str, Any]:
        return generate_target_metrics(current)
    
    def _generate_risks(self, analysis_result: Dict[str, Any]) -> List[Dict[str, str]]:
        return generate_risks(analysis_result)
    
    def _generate_success_criteria(self, metrics: Dict[str, Any]) -> List[str]:
        return generate_success_criteria(metrics)
    
    def _create_strategy_object(self, strategy_data: Dict[str, Any]) -> Strategy:
        return strategy_data
    
    def _make_serializable(self, obj: Any) -> Any:
        if hasattr(obj, '__dict__'):
            return {k: self._make_serializable(v) for k, v in obj.__dict__.items()}
        elif isinstance(obj, dict):
            return {k: self._make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._make_serializable(item) for item in obj]
        elif hasattr(obj, '__name__'):
            return str(obj)
        else:
            return obj

generator = PlanfileGenerator()
