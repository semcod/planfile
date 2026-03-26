#!/usr/bin/env python3
"""
Example 4: LLX Integration for Metric-Driven Planning
Demonstrates how planfile uses LLX for code analysis and model selection
"""

import json
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import yaml

@dataclass
class ProjectMetrics:
    """Project metrics from LLX analysis."""
    total_files: int
    total_lines: int
    avg_cc: float
    max_cc: int
    critical_count: int
    god_modules: int
    dup_groups: int
    languages: List[str]
    coupling_score: float
    cohesion_score: float

class LLXIntegration:
    """Integration with LLX for code analysis and model selection."""
    
    def __init__(self, llx_path: Optional[str] = None):
        self.llx_path = llx_path or "llx"
    
    def analyze_project(self, project_path: str, toon_dir: Optional[str] = None) -> ProjectMetrics:
        """Analyze project using LLX."""
        print(f"Analyzing project: {project_path}")
        
        # Try to use LLX if available
        try:
            cmd = [self.llx_path, "analyze", project_path]
            if toon_dir:
                cmd.extend(["--toon-dir", toon_dir])
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                # Parse LLX output
                return self._parse_llx_output(result.stdout)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("LLX not available, using basic analysis")
        
        # Fallback to basic analysis
        return self._basic_analysis(project_path)
    
    def _parse_llx_output(self, output: str) -> ProjectMetrics:
        """Parse LLX analysis output."""
        # This would parse actual LLX output format
        # For now, simulate based on typical LLX output
        lines = output.strip().split('\n')
        data = {}
        
        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                data[key.strip()] = value.strip()
        
        return ProjectMetrics(
            total_files=int(data.get('total_files', 0)),
            total_lines=int(data.get('total_lines', 0)),
            avg_cc=float(data.get('avg_cc', 0)),
            max_cc=int(data.get('max_cc', 0)),
            critical_count=int(data.get('critical_count', 0)),
            god_modules=int(data.get('god_modules', 0)),
            dup_groups=int(data.get('dup_groups', 0)),
            languages=data.get('languages', 'python').split(','),
            coupling_score=float(data.get('coupling', 0)),
            cohesion_score=float(data.get('cohesion', 0))
        )
    
    def _basic_analysis(self, project_path: str) -> ProjectMetrics:
        """Basic project analysis without LLX."""
        import os
        
        files = lines = 0
        max_cc = 0
        total_cc = 0
        cc_count = 0
        
        for root, dirs, fnames in os.walk(project_path):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
            
            for fname in fnames:
                if fname.endswith('.py'):
                    files += 1
                    filepath = Path(root) / fname
                    
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            content = f.read()
                            line_count = len(content.splitlines())
                            lines += line_count
                            
                            # Simple CC estimation (very basic)
                            cc = content.count(' if ') + content.count(' for ') + content.count(' while ') + 1
                            max_cc = max(max_cc, cc)
                            total_cc += cc
                            cc_count += 1
                    except Exception:
                        pass
        
        avg_cc = total_cc / cc_count if cc_count > 0 else 0
        
        return ProjectMetrics(
            total_files=files,
            total_lines=lines,
            avg_cc=avg_cc,
            max_cc=max_cc,
            critical_count=sum(1 for cc in [max_cc] if cc >= 15),
            god_modules=1 if lines > 500 else 0,  # Simplified
            dup_groups=0,  # Would need duplication analysis
            languages=['python'],
            coupling_score=0.5,  # Placeholder
            cohesion_score=0.5   # Placeholder
        )
    
    def select_model(self, metrics: ProjectMetrics, task_hint: str) -> str:
        """Select optimal model based on metrics and task type."""
        # This would use LLX's model selection logic
        # For now, implement simplified version
        
        # Base model selection on complexity
        if metrics.avg_cc > 8 or metrics.max_cc > 20:
            complexity_tier = "high"
        elif metrics.avg_cc > 4 or metrics.max_cc > 10:
            complexity_tier = "medium"
        else:
            complexity_tier = "low"
        
        # Task-specific adjustments
        task_models = {
            "planning": {
                "high": "anthropic/claude-opus-4",
                "medium": "anthropic/claude-sonnet-4",
                "low": "anthropic/claude-haiku-4.5"
            },
            "refactor": {
                "high": "anthropic/claude-opus-4",
                "medium": "anthropic/claude-sonnet-4",
                "low": "openai/gpt-4"
            },
            "test": {
                "high": "anthropic/claude-sonnet-4",
                "medium": "anthropic/claude-haiku-4.5",
                "low": "anthropic/claude-haiku-4.5"
            },
            "docs": {
                "high": "anthropic/claude-sonnet-4",
                "medium": "anthropic/claude-haiku-4.5",
                "low": "openai/gpt-3.5-turbo"
            }
        }
        
        return task_models.get(task_hint, task_models["refactor"]).get(complexity_tier, "anthropic/claude-sonnet-4")
    
    def get_task_scope(self, metrics: ProjectMetrics) -> Dict[str, int]:
        """Estimate task scope based on metrics."""
        # Simple heuristic for estimating tasks
        tasks = {
            "critical_refactors": metrics.critical_count + metrics.god_modules,
            "standard_refactors": max(0, metrics.total_files // 10 - metrics.critical_count),
            "test_writing": max(5, metrics.total_files // 5),
            "documentation": max(3, metrics.total_files // 15),
            "quality_gates": 3
        }
        return tasks

def example_metric_driven_planning():
    """Example: Generate strategy based on actual project metrics."""
    print("=" * 60)
    print("Metric-Driven Planning with LLX")
    print("=" * 60)
    
    llx = LLXIntegration()
    
    # Analyze a sample project
    project_path = "."
    print(f"\n1. Analyzing project at: {project_path}")
    
    metrics = llx.analyze_project(project_path)
    
    print("\nProject Metrics:")
    print(f"  Files: {metrics.total_files}")
    print(f"  Lines: {metrics.total_lines}")
    print(f"  Avg CC: {metrics.avg_cc:.1f}")
    print(f"  Max CC: {metrics.max_cc}")
    print(f"  Critical functions: {metrics.critical_count}")
    print(f"  God modules: {metrics.god_modules}")
    print(f"  Duplicate groups: {metrics.dup_groups}")
    print(f"  Languages: {', '.join(metrics.languages)}")
    print(f"  Coupling score: {metrics.coupling_score:.2f}")
    print(f"  Cohesion score: {metrics.cohesion_score:.2f}")
    
    # Get task scope estimates
    print("\n2. Estimating task scope...")
    task_scope = llx.get_task_scope(metrics)
    
    print("\nEstimated Tasks:")
    for task_type, count in task_scope.items():
        print(f"  {task_type}: {count}")
    
    # Select models for different tasks
    print("\n3. Selecting optimal models...")
    
    task_types = ["planning", "refactor", "test", "docs"]
    model_selections = {}
    
    for task_type in task_types:
        model = llx.select_model(metrics, task_type)
        model_selections[task_type] = model
        print(f"  {task_type}: {model}")
    
    # Generate strategy based on metrics
    print("\n4. Generating metric-driven strategy...")
    
    strategy = {
        "project": {
            "name": Path(project_path).name,
            "metrics": {
                "total_files": metrics.total_files,
                "total_lines": metrics.total_lines,
                "avg_cc": round(metrics.avg_cc, 2),
                "max_cc": metrics.max_cc,
                "complexity_score": _calculate_complexity_score(metrics)
            }
        },
        "sprints": [],
        "quality_gates": []
    }
    
    # Generate sprints based on metrics
    total_tasks = sum(task_scope.values())
    tasks_per_sprint = max(3, total_tasks // 3)
    
    # Sprint 1: Critical issues
    sprint1_tasks = []
    if metrics.critical_count > 0:
        sprint1_tasks.append({
            "name": f"Fix {metrics.critical_count} critical functions (CC≥15)",
            "task_type": "refactor",
            "priority": "critical",
            "estimated_hours": metrics.critical_count * 4,
            "model_hints": {
                "planning": model_selections["refactor"],
                "implementation": model_selections["refactor"],
                "review": model_selections["refactor"]
            }
        })
    
    if metrics.god_modules > 0:
        sprint1_tasks.append({
            "name": f"Split {metrics.god_modules} god modules",
            "task_type": "refactor",
            "priority": "critical",
            "estimated_hours": metrics.god_modules * 8,
            "model_hints": {
                "planning": model_selections["refactor"],
                "implementation": model_selections["refactor"],
                "review": model_selections["refactor"]
            }
        })
    
    strategy["sprints"].append({
        "id": "sprint-1",
        "name": "Critical Complexity Reduction",
        "goal": f"Reduce max CC from {metrics.max_cc} to <15",
        "task_patterns": sprint1_tasks
    })
    
    # Sprint 2: Systematic improvements
    sprint2_tasks = []
    if metrics.dup_groups > 0:
        sprint2_tasks.append({
            "name": f"Eliminate {metrics.dup_groups} duplicate code groups",
            "task_type": "refactor",
            "priority": "high",
            "estimated_hours": metrics.dup_groups * 3,
            "model_hints": {
                "planning": model_selections["refactor"],
                "implementation": model_selections["refactor"],
                "review": model_selections["test"]
            }
        })
    
    sprint2_tasks.append({
        "name": "Improve code structure and patterns",
        "task_type": "refactor",
        "priority": "medium",
        "estimated_hours": max(8, metrics.total_files // 10),
        "model_hints": {
            "planning": model_selections["planning"],
            "implementation": model_selections["refactor"],
            "review": model_selections["refactor"]
        }
    })
    
    strategy["sprints"].append({
        "id": "sprint-2",
        "name": "Code Quality Enhancement",
        "goal": "Improve maintainability and reduce duplication",
        "task_patterns": sprint2_tasks
    })
    
    # Sprint 3: Testing and documentation
    sprint3_tasks = [
        {
            "name": f"Add comprehensive test suite ({task_scope['test_writing']} tests)",
            "task_type": "test",
            "priority": "high",
            "estimated_hours": task_scope["test_writing"] * 2,
            "model_hints": {
                "planning": model_selections["test"],
                "implementation": model_selections["test"],
                "review": model_selections["test"]
            }
        },
        {
            "name": f"Generate documentation ({task_scope['documentation']} docs)",
            "task_type": "docs",
            "priority": "medium",
            "estimated_hours": task_scope["documentation"] * 3,
            "model_hints": {
                "planning": model_selections["docs"],
                "implementation": model_selections["docs"],
                "review": model_selections["docs"]
            }
        }
    ]
    
    strategy["sprints"].append({
        "id": "sprint-3",
        "name": "Testing & Documentation",
        "goal": "Achieve 80% test coverage and complete documentation",
        "task_patterns": sprint3_tasks
    })
    
    # Add quality gates based on current metrics
    strategy["quality_gates"] = [
        {
            "name": "Cyclomatic Complexity",
            "metric": "avg_cc",
            "threshold": max(3.0, metrics.avg_cc * 0.6),
            "operator": "<=",
            "current": metrics.avg_cc
        },
        {
            "name": "Test Coverage",
            "metric": "test_coverage",
            "threshold": 80,
            "operator": ">=",
            "current": 0  # Would need actual coverage analysis
        },
        {
            "name": "Code Duplication",
            "metric": "duplication_percent",
            "threshold": 5,
            "operator": "<=",
            "current": metrics.dup_groups * 10  # Rough estimate
        }
    ]
    
    # Save strategy
    with open("llx-driven-strategy.yaml", "w") as f:
        yaml.dump(strategy, f, default_flow_style=False, indent=2)
    
    print(f"\n✅ Strategy saved to: llx-driven-strategy.yaml")
    
    # Summary
    print("\n5. Strategy Summary:")
    print(f"  Total sprints: {len(strategy['sprints'])}")
    total_tasks = sum(len(s['task_patterns']) for s in strategy['sprints'])
    print(f"  Total tasks: {total_tasks}")
    total_hours = sum(
        sum(t.get('estimated_hours', 0) for t in s['task_patterns'])
        for s in strategy['sprints']
    )
    print(f"  Estimated hours: {total_hours}")
    print(f"  Quality gates: {len(strategy['quality_gates'])}")

def _calculate_complexity_score(metrics: ProjectMetrics) -> float:
    """Calculate overall complexity score (0-100)."""
    # Weight different factors
    cc_score = min(100, metrics.avg_cc * 10)  # 40% weight
    size_score = min(100, metrics.total_lines / 100)  # 30% weight
    structure_score = (metrics.god_modules * 20 + metrics.critical_count * 15)  # 30% weight
    
    return (cc_score * 0.4 + size_score * 0.3 + structure_score * 0.3)

def create_llx_config_example():
    """Create example LLX configuration for planfile integration."""
    config = {
        "analysis": {
            "tools": ["code2llm", "redup", "vallm"],
            "exclude_patterns": [
                "*/__pycache__/*",
                "*/venv/*",
                "*/.tox/*",
                "*/tests/*"
            ],
            "metrics": {
                "complexity": {
                    "tool": "code2llm",
                    "threshold": {
                        "low": 5,
                        "medium": 10,
                        "high": 15
                    }
                },
                "duplication": {
                    "tool": "redup",
                    "min_lines": 10,
                    "min_duplicates": 2
                },
                "coverage": {
                    "tool": "vallm",
                    "exclude_test_files": False
                }
            }
        },
        "model_selection": {
            "rules": [
                {
                    "name": "high_complexity_refactor",
                    "conditions": {
                        "avg_cc": {"gt": 8},
                        "max_cc": {"gt": 20},
                        "god_modules": {"gt": 0}
                    },
                    "models": ["anthropic/claude-opus-4"],
                    "reasoning": "High complexity requires strongest model"
                },
                {
                    "name": "medium_complexity_refactor",
                    "conditions": {
                        "avg_cc": {"gt": 4, "lte": 8},
                        "total_files": {"gt": 20}
                    },
                    "models": ["anthropic/claude-sonnet-4", "openai/gpt-4"],
                    "reasoning": "Medium complexity needs balanced model"
                },
                {
                    "name": "low_complexity_tasks",
                    "conditions": {
                        "avg_cc": {"lte": 4},
                        "task_type": ["test", "docs"]
                    },
                    "models": ["anthropic/claude-haiku-4.5", "openai/gpt-3.5-turbo"],
                    "reasoning": "Simple tasks can use cheaper models"
                }
            ],
            "fallback": "anthropic/claude-sonnet-4"
        },
        "integration": {
            "planfile": {
                "auto_analyze": True,
                "cache_metrics": True,
                "cache_ttl": 3600,
                "export_format": "yaml"
            }
        }
    }
    
    with open("llx-config-for-planfile.yaml", "w") as f:
        yaml.dump(config, f, default_flow_style=False, indent=2)
    
    print("\n✅ LLX configuration saved to: llx-config-for-planfile.yaml")

if __name__ == "__main__":
    example_metric_driven_planning()
    create_llx_config_example()
    
    print("\n\n" + "=" * 60)
    print("LLX Integration Benefits")
    print("=" * 60)
    print("""
    1. Metric-driven decisions based on actual code analysis
    2. Optimal model selection saves cost without sacrificing quality
    3. Automated task scope estimation
    4. Quality gates tailored to current state
    5. Continuous improvement through feedback loop
    
    LLX + planfile = Intelligent, data-driven refactoring!
    """)
