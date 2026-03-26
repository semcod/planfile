#!/usr/bin/env python3
"""
Comprehensive Planfile Generation from File Analysis
Combines file analysis with intelligent planfile generation.
"""

import os
import sys
import json
import yaml
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

# Import our analyzer
from enhanced_analyze import EnhancedFileAnalyzer, SprintGenerator


class PlanfileFromFiles:
    """Generate comprehensive planfile from file analysis."""
    
    def __init__(self):
        self.analyzer = EnhancedFileAnalyzer()
        self.generator = SprintGenerator()
    
    def generate_planfile(self, 
                         analysis_path: str,
                         output_file: str = "planfile-from-files.yaml",
                         project_name: str = None,
                         max_sprints: int = 4) -> Dict[str, Any]:
        """Generate planfile from analyzed files."""
        
        print("=" * 60)
        print("COMPREHENSIVE PLANFILE GENERATION FROM FILES")
        print("=" * 60)
        
        # Analyze files
        print(f"\n🔍 Analyzing files in {analysis_path}...")
        analysis_result = self.analyzer.analyze_directory(Path(analysis_path))
        
        # Get summary
        summary = analysis_result['summary']
        print(f"\n📊 Analysis Results:")
        print(f"  Files analyzed: {len(analysis_result['analyzed_files'])}")
        print(f"  Total issues: {summary['total_issues']}")
        print(f"  Critical: {summary['priority_breakdown']['critical']}")
        print(f"  High: {summary['priority_breakdown']['high']}")
        print(f"  Medium: {summary['priority_breakdown']['medium']}")
        print(f"  Low: {summary['priority_breakdown']['low']}")
        
        # Generate sprints
        print(f"\n🏃 Generating sprints...")
        sprints = self.generator.generate_sprints(analysis_result, max_sprints)
        
        # Generate tickets
        print(f"🎫 Organizing tickets...")
        tickets = self.generator.generate_tickets(analysis_result)
        
        # Extract key metrics for quality gates
        metrics = self._extract_key_metrics(analysis_result)
        
        # Create comprehensive planfile
        project_name = project_name or Path(analysis_path).name
        
        planfile = {
            'name': f'{project_name.title()} Improvement Plan',
            'project_name': project_name,
            'project_type': 'improvement',
            'domain': 'software',
            'goal': 'Systematically address issues found in file analysis',
            
            'goals': self._generate_goals(summary, metrics),
            
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
        
        # Save planfile
        output_path = Path(output_file)
        print(f"\n💾 Saving planfile to {output_path}...")
        
        with open(output_path, 'w') as f:
            yaml.dump(planfile, f, default_flow_style=False, sort_keys=False)
        
        # Print summary
        self._print_planfile_summary(planfile)
        
        return planfile
    
    def _extract_key_metrics(self, analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract key metrics from analysis."""
        metrics = {}
        
        # Extract CC metrics
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
    
    def _generate_goals(self, summary: Dict[str, Any], metrics: Dict[str, Any]) -> List[str]:
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
        
        # Add general goals
        goals.append("Improve overall code quality")
        goals.append("Ensure all files pass validation")
        
        return goals
    
    def _generate_quality_gates(self, metrics: Dict[str, Any]) -> List[Dict[str, str]]:
        """Generate quality gates based on current metrics."""
        gates = []
        
        if 'average_cc' in metrics:
            gates.append({
                'metric': 'Average Cyclomatic Complexity',
                'threshold': '≤ 3.5'
            })
        
        gates.append({
            'metric': 'Critical Functions',
            'threshold': '0'
        })
        
        gates.append({
            'metric': 'Validation Errors',
            'threshold': '0'
        })
        
        gates.append({
            'metric': 'Validation Warnings',
            'threshold': '0'
        })
        
        if 'duplication_groups' in metrics:
            gates.append({
                'metric': 'Code Duplication',
                'threshold': '0 groups'
            })
        
        gates.append({
            'metric': 'Test Coverage',
            'threshold': '≥ 80%'
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
    
    def _print_planfile_summary(self, planfile: Dict[str, Any]):
        """Print summary of generated planfile."""
        print("\n" + "=" * 60)
        print("PLANFILE GENERATION SUMMARY")
        print("=" * 60)
        
        print(f"\n📋 Planfile: {planfile['name']}")
        print(f"🎯 Goal: {planfile['goal']}")
        
        print(f"\n📈 Metrics:")
        for key, value in planfile['metrics']['current'].items():
            target = planfile['metrics']['target'].get(key, 'N/A')
            print(f"  {key}: {value} → {target}")
        
        print(f"\n🏃 Sprints: {len(planfile['sprints'])}")
        for sprint in planfile['sprints']:
            print(f"  - {sprint['name']} ({sprint['duration']}) - {sprint['issue_count']} issues")
        
        print(f"\n🎫 Tickets:")
        for priority, tickets in planfile['tickets'].items():
            if tickets:
                print(f"  - {priority.title()}: {len(tickets)} tickets")
        
        print(f"\n✅ Success Criteria: {len(planfile['success_criteria'])} items")
        print(f"⚠️  Risks: {len(planfile['risks'])} identified")


def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(
        description="Generate comprehensive planfile from file analysis"
    )
    
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Path to analyze (default: current directory)"
    )
    
    parser.add_argument(
        "--output",
        "-o",
        default="planfile-from-files.yaml",
        help="Output planfile name"
    )
    
    parser.add_argument(
        "--project-name",
        "-p",
        help="Project name (default: directory name)"
    )
    
    parser.add_argument(
        "--max-sprints",
        type=int,
        default=4,
        help="Maximum number of sprints"
    )
    
    parser.add_argument(
        "--patterns",
        nargs="+",
        default=["*.yaml", "*.yml", "*.json", "*.toon.yaml", "*.toon.yml"],
        help="File patterns to analyze"
    )
    
    args = parser.parse_args()
    
    # Generate planfile
    generator = PlanfileFromFiles()
    planfile = generator.generate_planfile(
        analysis_path=args.path,
        output_file=args.output,
        project_name=args.project_name,
        max_sprints=args.max_sprints
    )
    
    print(f"\n✅ Planfile successfully generated: {args.output}")
    
    # Suggest next steps
    print(f"\n📋 Next Steps:")
    print(f"1. Review generated planfile: {args.output}")
    print(f"2. Validate: python3 -m planfile.cli.commands validate {args.output}")
    print(f"3. Apply (dry run): python3 -m planfile.cli.commands apply {args.output} . --dry-run")
    print(f"4. Execute sprints using your project management tool")


if __name__ == "__main__":
    main()
