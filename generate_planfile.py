#!/usr/bin/env python3
"""
Automated Planfile Generation Algorithm
Runs analysis commands and generates planfile.yaml based on results.
"""

import os
import sys
import subprocess
import yaml
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import re


class PlanfileGenerator:
    """Automated planfile generation from project analysis."""
    
    def __init__(self, project_path: str = "."):
        self.project_path = Path(project_path)
        self.output_dir = self.project_path / "project"
        self.output_dir.mkdir(exist_ok=True)
        
        # Analysis results
        self.code2llm_results = None
        self.vallm_results = None
        self.redup_results = None
        
        # Generated planfile data
        self.planfile_data = {}
    
    def run_code2llm(self) -> Dict[str, Any]:
        """Run code2llm analysis."""
        print("🔍 Running code2llm analysis...")
        
        cmd = [
            "venv/bin/code2llm",
            str(self.project_path),
            "-f", "all",
            "-o", str(self.output_dir),
            "--no-chunk"
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode == 0:
                print("✅ code2llm completed successfully")
                return self.parse_code2llm_output()
            else:
                print(f"❌ code2llm failed: {result.stderr}")
                return {}
        except subprocess.TimeoutExpired:
            print("⏰ code2llm timed out")
            return {}
        except FileNotFoundError:
            print("⚠️  code2llm not found, using mock data")
            return self.get_mock_code2llm_data()
    
    def run_vallm(self) -> Dict[str, Any]:
        """Run vallm validation."""
        print("🔍 Running vallm validation...")
        
        cmd = [
            "venv/bin/vallm",
            "batch",
            str(self.project_path),
            "--recursive",
            "--format", "toon",
            "--output", str(self.output_dir)
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode == 0:
                print("✅ vallm completed successfully")
                return self.parse_vallm_output()
            else:
                print(f"❌ vallm failed: {result.stderr}")
                return {}
        except subprocess.TimeoutExpired:
            print("⏰ vallm timed out")
            return {}
        except FileNotFoundError:
            print("⚠️  vallm not found, using mock data")
            return self.get_mock_vallm_data()
    
    def run_redup(self) -> Dict[str, Any]:
        """Run redup duplication analysis."""
        print("🔍 Running redup analysis...")
        
        cmd = [
            "venv/bin/redup",
            "scan",
            str(self.project_path),
            "--format", "toon",
            "--output", str(self.output_dir)
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode == 0:
                print("✅ redup completed successfully")
                return self.parse_redup_output()
            else:
                print(f"❌ redup failed: {result.stderr}")
                return {}
        except subprocess.TimeoutExpired:
            print("⏰ redup timed out")
            return {}
        except FileNotFoundError:
            print("⚠️  redup not found, using mock data")
            return self.get_mock_redup_data()
    
    def parse_code2llm_output(self) -> Dict[str, Any]:
        """Parse code2llm analysis.toon.yaml output."""
        analysis_file = self.output_dir / "analysis.toon.yaml"
        
        if not analysis_file.exists():
            return self.get_mock_code2llm_data()
        
        with open(analysis_file, 'r') as f:
            content = f.read()
        
        # Extract metrics from header
        header = content.split('\n')[0]
        metrics = {}
        
        # Parse CC average
        cc_match = re.search(r'CC̄=(\d+\.?\d*)', header)
        if cc_match:
            metrics['cc_average'] = float(cc_match.group(1))
        
        # Parse critical count
        critical_match = re.search(r'critical:(\d+)', header)
        if critical_match:
            metrics['critical_functions'] = int(critical_match.group(1))
        
        # Parse high-CC functions
        high_cc_functions = []
        for line in content.split('\n'):
            if 'CC=' in line and 'limit:15' in line:
                func_match = re.search(r'(\w+)\s+CC=(\d+)', line)
                if func_match:
                    high_cc_functions.append({
                        'name': func_match.group(1),
                        'cc': int(func_match.group(2))
                    })
        
        metrics['high_cc_functions'] = high_cc_functions
        
        return metrics
    
    def parse_vallm_output(self) -> Dict[str, Any]:
        """Parse vallm validation.toon.yaml output."""
        validation_file = self.output_dir / "validation.toon.yaml"
        
        if not validation_file.exists():
            return self.get_mock_vallm_data()
        
        with open(validation_file, 'r') as f:
            content = f.read()
        
        metrics = {}
        
        # Parse summary
        summary_match = re.search(r'scanned: (\d+)\s+passed: (\d+)\s+\((\d+\.?\d*)%\)\s+warnings: (\d+)\s+errors: (\d+)', content)
        if summary_match:
            metrics['total_files'] = int(summary_match.group(1))
            metrics['passed_files'] = int(summary_match.group(2))
            metrics['pass_rate'] = float(summary_match.group(3))
            metrics['warnings'] = int(summary_match.group(4))
            metrics['errors'] = int(summary_match.group(5))
        
        # Extract error details
        error_details = []
        in_errors = False
        for line in content.split('\n'):
            if 'ERRORS[' in line:
                in_errors = True
                continue
            elif 'WARNINGS[' in line:
                in_errors = False
                continue
            elif in_errors and line.strip() and not line.startswith('  '):
                break
            elif in_errors and '.py' in line:
                file_match = re.search(r'([^,]+),(\d+\.?\d*)', line)
                if file_match:
                    error_details.append({
                        'file': file_match.group(1),
                        'score': float(file_match.group(2))
                    })
        
        metrics['error_details'] = error_details
        
        return metrics
    
    def parse_redup_output(self) -> Dict[str, Any]:
        """Parse redup duplication.toon.yaml output."""
        dup_file = self.output_dir / "duplication.toon.yaml"
        
        if not dup_file.exists():
            return self.get_mock_redup_data()
        
        with open(dup_file, 'r') as f:
            content = f.read()
        
        metrics = {}
        
        # Parse summary
        dup_match = re.search(r'dup_groups:\s+(\d+)', content)
        if dup_match:
            metrics['duplication_groups'] = int(dup_match.group(1))
        
        saved_match = re.search(r'saved_lines:\s+(\d+)', content)
        if saved_match:
            metrics['saved_lines'] = int(saved_match.group(1))
        
        # Extract duplicate details
        dup_details = []
        in_dup = False
        for line in content.split('\n'):
            if 'DUPLICATES[' in line:
                in_dup = True
                continue
            elif 'REFACTOR[' in line:
                in_dup = False
                continue
            elif in_dup and 'EXAC' in line:
                parts = line.split()
                if len(parts) >= 6:
                    dup_details.append({
                        'type': parts[2],
                        'function': parts[3],
                        'lines': int(parts[4].split('=')[1]),
                        'occurrences': int(parts[5].split('=')[1])
                    })
        
        metrics['duplicate_details'] = dup_details
        
        return metrics
    
    def get_mock_code2llm_data(self) -> Dict[str, Any]:
        """Mock code2llm data for testing."""
        return {
            'cc_average': 4.1,
            'critical_functions': 12,
            'high_cc_functions': [
                {'name': 'generate_report', 'cc': 20},
                {'name': 'update_ticket', 'cc': 15},
                {'name': 'table', 'cc': 21},
                {'name': 'filter_handler', 'cc': 21}
            ]
        }
    
    def get_mock_vallm_data(self) -> Dict[str, Any]:
        """Mock vallm data for testing."""
        return {
            'total_files': 103,
            'passed_files': 41,
            'pass_rate': 39.8,
            'warnings': 5,
            'errors': 33,
            'error_details': [
                {'file': 'examples/demo_without_keys.py', 'score': 0.0},
                {'file': 'planfile/__init__.py', 'score': 0.57}
            ]
        }
    
    def get_mock_redup_data(self) -> Dict[str, Any]:
        """Mock redup data for testing."""
        return {
            'duplication_groups': 1,
            'saved_lines': 6,
            'duplicate_details': [
                {
                    'type': 'EXAC',
                    'function': 'get_sprint',
                    'lines': 6,
                    'occurrences': 2
                }
            ]
        }
    
    def generate_planfile(self) -> Dict[str, Any]:
        """Generate planfile based on analysis results."""
        print("\n📝 Generating planfile...")
        
        # Get project name from directory
        project_name = self.project_path.name
        
        # Base planfile structure
        planfile = {
            'name': f'{project_name.title()} Code Quality Improvement',
            'project_name': project_name,
            'project_type': 'refactoring',
            'domain': 'dev-tools',
            'goal': 'Reduce complexity and improve code quality based on automated analysis',
            
            'goals': [
                f"Reduce cyclomatic complexity from {self.code2llm_results.get('cc_average', 0):.1f} to ≤ 3.5",
                f"Fix all {self.vallm_results.get('errors', 0)} validation errors",
                f"Resolve {self.vallm_results.get('warnings', 0)} validation warnings",
                f"Remove {self.redup_results.get('duplication_groups', 0)} code duplication groups",
                "Improve test coverage to ≥ 80%",
                "Ensure all imports are resolvable"
            ],
            
            'quality_gates': [
                {'metric': 'Average Cyclomatic Complexity', 'threshold': '≤ 3.5'},
                {'metric': 'High-CC Functions', 'threshold': '0'},
                {'metric': 'Validation Errors', 'threshold': '0'},
                {'metric': 'Validation Warnings', 'threshold': '0'},
                {'metric': 'Test Coverage', 'threshold': '≥ 80%'},
                {'metric': 'Code Duplication', 'threshold': '0 groups'}
            ],
            
            'sprints': self.generate_sprints(),
            'tasks': self.generate_tasks(),
            'metrics': self.generate_metrics(),
            'tickets': self.generate_tickets()
        }
        
        return planfile
    
    def generate_sprints(self) -> List[Dict[str, Any]]:
        """Generate sprint definitions."""
        sprints = []
        
        # Sprint 1: Critical Issues
        sprint1 = {
            'id': 'sprint-1',
            'name': 'Critical Issues Resolution',
            'duration': '2 weeks',
            'objectives': [
                f"Fix {self.vallm_results.get('errors', 0)} validation errors",
                f"Split {len(self.code2llm_results.get('high_cc_functions', []))} high-CC functions",
                f"Remove {self.redup_results.get('duplication_groups', 0)} duplication groups",
                "Resolve import issues"
            ],
            'task_patterns': [
                {
                    'name': 'Fix validation errors',
                    'description': 'Resolve all syntax and import errors',
                    'task_type': 'bugfix',
                    'priority': 'critical',
                    'estimate': f"{max(1, self.vallm_results.get('errors', 0) // 10)}d",
                    'model_hints': {'planning': 'balanced', 'implementation': 'balanced'}
                },
                {
                    'name': 'Refactor high-CC functions',
                    'description': 'Split functions with CC > 15',
                    'task_type': 'refactor',
                    'priority': 'critical',
                    'estimate': f"{max(2, len(self.code2llm_results.get('high_cc_functions', [])))}d",
                    'model_hints': {'planning': 'premium', 'implementation': 'premium'}
                }
            ]
        }
        sprints.append(sprint1)
        
        # Sprint 2: Quality Improvements
        sprint2 = {
            'id': 'sprint-2',
            'name': 'Quality Improvements',
            'duration': '2 weeks',
            'objectives': [
                f"Address {self.vallm_results.get('warnings', 0)} validation warnings",
                "Improve test coverage",
                "Add documentation"
            ],
            'task_patterns': [
                {
                    'name': 'Fix validation warnings',
                    'description': 'Address all validation warnings',
                    'task_type': 'refactor',
                    'priority': 'high',
                    'estimate': f"{max(1, self.vallm_results.get('warnings', 0))}d",
                    'model_hints': {'planning': 'balanced', 'implementation': 'balanced'}
                },
                {
                    'name': 'Improve test coverage',
                    'description': 'Add comprehensive tests',
                    'task_type': 'test',
                    'priority': 'high',
                    'estimate': '5d',
                    'model_hints': {'planning': 'balanced', 'implementation': 'balanced'}
                }
            ]
        }
        sprints.append(sprint2)
        
        # Sprint 3: Polish and Release
        sprint3 = {
            'id': 'sprint-3',
            'name': 'Polish and Release',
            'duration': '1 week',
            'objectives': [
                "Performance optimization",
                "Documentation updates",
                "Release preparation"
            ],
            'task_patterns': [
                {
                    'name': 'Performance optimization',
                    'description': 'Optimize bottlenecks',
                    'task_type': 'optimize',
                    'priority': 'medium',
                    'estimate': '2d',
                    'model_hints': {'planning': 'balanced', 'implementation': 'balanced'}
                },
                {
                    'name': 'Update documentation',
                    'description': 'Update API docs and README',
                    'task_type': 'documentation',
                    'priority': 'low',
                    'estimate': '1d',
                    'model_hints': {'planning': 'balanced', 'implementation': 'balanced'}
                }
            ]
        }
        sprints.append(sprint3)
        
        return sprints
    
    def generate_tasks(self) -> Dict[str, List[Dict[str, Any]]]:
        """Generate task breakdowns."""
        tasks = {
            'critical_refactors': [],
            'standard_refactors': [],
            'test_writing': [],
            'documentation': []
        }
        
        # Critical refactors from high-CC functions
        for func in self.code2llm_results.get('high_cc_functions', [])[:5]:
            tasks['critical_refactors'].append({
                'name': f"Refactor {func['name']} (CC={func['cc']})",
                'description': f"Split function with high cyclomatic complexity",
                'estimated_hours': func['cc'] * 0.5,
                'complexity': 'high' if func['cc'] > 18 else 'medium'
            })
        
        # Standard refactors for duplicates
        for dup in self.redup_results.get('duplicate_details', []):
            tasks['standard_refactors'].append({
                'name': f"Extract {dup['function']} utility",
                'description': f"Remove duplication ({dup['occurrences']} occurrences)",
                'estimated_hours': dup['lines'] * 0.5,
                'complexity': 'low'
            })
        
        # Test writing
        tasks['test_writing'].append({
            'name': 'Add unit tests',
            'description': 'Comprehensive test suite',
            'estimated_hours': 20,
            'complexity': 'medium'
        })
        
        # Documentation
        tasks['documentation'].append({
            'name': 'Update API documentation',
            'description': 'Document all modules and functions',
            'estimated_hours': 8,
            'complexity': 'low'
        })
        
        return tasks
    
    def generate_metrics(self) -> Dict[str, Any]:
        """Generate metrics section."""
        return {
            'current': {
                'cc_average': self.code2llm_results.get('cc_average', 0),
                'high_cc_functions': len(self.code2llm_results.get('high_cc_functions', [])),
                'validation_errors': self.vallm_results.get('errors', 0),
                'validation_warnings': self.vallm_results.get('warnings', 0),
                'duplication_groups': self.redup_results.get('duplication_groups', 0),
                'pass_rate': self.vallm_results.get('pass_rate', 0)
            },
            'target': {
                'cc_average': 3.5,
                'high_cc_functions': 0,
                'validation_errors': 0,
                'validation_warnings': 0,
                'duplication_groups': 0,
                'pass_rate': 100
            }
        }
    
    def generate_tickets(self) -> Dict[str, List[Dict[str, Any]]]:
        """Generate ticket definitions."""
        tickets = {
            'high_priority': [],
            'medium_priority': [],
            'low_priority': []
        }
        
        # High priority tickets
        if self.vallm_results.get('errors', 0) > 0:
            tickets['high_priority'].append({
                'title': f"Fix {self.vallm_results.get('errors', 0)} validation errors",
                'description': 'Resolve all syntax and import errors',
                'priority': 'highest',
                'labels': ['bugfix', 'validation']
            })
        
        if len(self.code2llm_results.get('high_cc_functions', [])) > 0:
            tickets['high_priority'].append({
                'title': f"Refactor {len(self.code2llm_results.get('high_cc_functions', []))} high-CC functions",
                'description': 'Reduce cyclomatic complexity',
                'priority': 'high',
                'labels': ['complexity', 'refactor']
            })
        
        # Medium priority
        if self.vallm_results.get('warnings', 0) > 0:
            tickets['medium_priority'].append({
                'title': f"Address {self.vallm_results.get('warnings', 0)} validation warnings",
                'description': 'Fix long functions and other warnings',
                'priority': 'medium',
                'labels': ['warning', 'refactor']
            })
        
        # Low priority
        tickets['low_priority'].append({
            'title': 'Improve documentation',
            'description': 'Update API docs and examples',
            'priority': 'low',
            'labels': ['documentation']
        })
        
        return tickets
    
    def save_planfile(self, planfile: Dict[str, Any], filename: str = "planfile.yaml"):
        """Save generated planfile."""
        output_path = self.project_path / filename
        
        with open(output_path, 'w') as f:
            yaml.dump(planfile, f, default_flow_style=False, sort_keys=False)
        
        print(f"✅ Planfile saved to: {output_path}")
        return output_path
    
    def run(self) -> str:
        """Run the complete generation process."""
        print("=" * 60)
        print("AUTOMATED PLANFILE GENERATION")
        print("=" * 60)
        
        # Run all analyses
        self.code2llm_results = self.run_code2llm()
        self.vallm_results = self.run_vallm()
        self.redup_results = self.run_redup()
        
        # Generate planfile
        planfile = self.generate_planfile()
        
        # Save planfile
        output_path = self.save_planfile(planfile)
        
        # Print summary
        print("\n📊 Generation Summary:")
        print(f"  - CC Average: {self.code2llm_results.get('cc_average', 'N/A')}")
        print(f"  - High-CC Functions: {len(self.code2llm_results.get('high_cc_functions', []))}")
        print(f"  - Validation Errors: {self.vallm_results.get('errors', 0)}")
        print(f"  - Validation Warnings: {self.vallm_results.get('warnings', 0)}")
        print(f"  - Duplication Groups: {self.redup_results.get('duplication_groups', 0)}")
        print(f"  - Sprints Generated: {len(planfile['sprints'])}")
        print(f"  - Total Tasks: {sum(len(tasks) for tasks in planfile['tasks'].values())}")
        
        return str(output_path)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate planfile from project analysis")
    parser.add_argument(
        "--project-path",
        default=".",
        help="Path to project directory (default: current)"
    )
    parser.add_argument(
        "--output",
        default="planfile.yaml",
        help="Output filename (default: planfile.yaml)"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock data instead of running analysis"
    )
    
    args = parser.parse_args()
    
    generator = PlanfileGenerator(args.project_path)
    
    if args.mock:
        print("⚠️  Using mock data")
        generator.code2llm_results = generator.get_mock_code2llm_data()
        generator.vallm_results = generator.get_mock_vallm_data()
        generator.redup_results = generator.get_mock_redup_data()
        planfile = generator.generate_planfile()
        generator.save_planfile(planfile, args.output)
    else:
        generator.run()
    
    print("\n✅ Planfile generation complete!")


if __name__ == "__main__":
    main()
