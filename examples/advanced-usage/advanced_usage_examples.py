#!/usr/bin/env python3
"""
Advanced usage examples for planfile.
Shows complex workflows and customizations.
"""

import sys
from pathlib import Path
from typing import Dict, List, Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from planfile import Strategy
from planfile.analysis.generator import generator
from planfile.analysis.file_analyzer import FileAnalyzer
from planfile.loaders.yaml_loader import save_strategy_yaml, load_strategy_yaml


def example_1_custom_file_patterns():
    """Example 1: Analyze with custom file patterns."""
    print("=" * 60)
    print("EXAMPLE 1: Custom File Patterns Analysis")
    print("=" * 60)
    
    # Custom patterns for different file types
    custom_patterns = [
        "*.py",       # Python files
        "*.js",       # JavaScript files
        "*.ts",       # TypeScript files
        "*.yaml",     # YAML configs
        "*.yml",      # YAML configs
        "*.json",     # JSON configs
        "Dockerfile", # Docker files
        "*.md",       # Documentation
    ]
    
    analyzer = FileAnalyzer()
    
    # Analyze with custom patterns
    result = analyzer.analyze_directory(
        Path("../../planfile"),
        patterns=custom_patterns
    )
    
    print(f"Analyzed with custom patterns:")
    print(f"  Files analyzed: {result['summary']['total_files']}")
    print(f"  Issues found: {result['summary']['total_issues']}")
    print(f"  Metrics: {result['summary']['total_metrics']}")
    
    # Priority breakdown
    priority = result['summary']['priority_breakdown']
    print(f"\nPriority Breakdown:")
    for p, count in priority.items():
        if count > 0:
            print(f"  {p}: {count}")
    
    # Generate strategy from custom analysis
    strategy = generator.generate_from_analysis(
        analysis_path="../../planfile",
        project_name="custom-patterns-analysis",
        max_sprints=3
    )
    
    save_strategy_yaml(strategy, "custom-patterns-strategy.yaml")
    print(f"\n✓ Strategy saved: custom-patterns-strategy.yaml")
    
    return result


def example_2_focus_area_strategies():
    """Example 2: Generate strategies for different focus areas."""
    print("\n" + "=" * 60)
    print("EXAMPLE 2: Focus Area Strategies")
    print("=" * 60)
    
    focus_areas = ["quality", "security", "performance", "testing", "documentation"]
    
    for focus in focus_areas:
        print(f"\n🎯 Generating {focus}-focused strategy...")
        
        try:
            strategy = generator.generate_from_current_project(
                project_path="../../planfile",
                project_name=f"planfile-{focus}-focus",
                max_sprints=2,
                focus_area=focus
            )
            
            # Save with focus-specific name
            filename = f"focus-{focus}-strategy.yaml"
            save_strategy_yaml(strategy, filename)
            
            # Show key metrics
            sprints = strategy.get('sprints', [])
            quality_gates = strategy.get('quality_gates', [])
            
            print(f"  ✓ Sprints: {len(sprints)}")
            print(f"  ✓ Quality Gates: {len(quality_gates)}")
            
            # Show first sprint objective
            if sprints:
                objectives = sprints[0].get('objectives', [])
                if objectives:
                    print(f"  • First objective: {objectives[0]}")
            
        except Exception as e:
            print(f"  ✗ Failed: {e}")
    
    print(f"\n✓ Generated {len(focus_areas)} focus-specific strategies")


def example_3_iterative_refinement():
    """Example 3: Iteratively refine a strategy."""
    print("\n" + "=" * 60)
    print("EXAMPLE 3: Iterative Strategy Refinement")
    print("=" * 60)
    
    # Generate initial strategy
    print("1. Generating initial strategy...")
    initial = generator.generate_from_current_project(
        project_path="../../planfile",
        project_name="iterative-example",
        max_sprints=5,
        focus_area="quality"
    )
    
    print(f"   Initial: {len(initial.get('sprints', []))} sprints")
    
    # Load and modify
    save_strategy_yaml(initial, "iterative-v1.yaml")
    
    # Load as Strategy object for manipulation
    strategy = load_strategy_yaml("iterative-v1.yaml")
    
    # Add custom quality gate
    from planfile.models_v2 import QualityGate
    strategy.quality_gates.append(
        QualityGate(
            name="Documentation Coverage",
            description="All public APIs must have documentation",
            criteria=["doc_coverage >= 90%"],
            required=True
        )
    )
    
    # Modify sprint duration
    for sprint in strategy.sprints:
        if hasattr(sprint, 'duration'):
            if 'week' in sprint.duration:
                weeks = int(sprint.duration.split()[0])
                sprint.duration = f"{weeks + 1} weeks"  # Add 1 week to each
    
    print("2. Modified strategy:")
    print(f"   Quality gates: {len(strategy.quality_gates)}")
    print(f"   Sprint durations extended")
    
    # Save modified version
    strategy.export("yaml")
    with open("iterative-v2.yaml", "w") as f:
        f.write(strategy.export("yaml"))
    
    # Compare versions
    v1 = load_strategy_yaml("iterative-v1.yaml")
    comparison = v1.compare(strategy)
    
    print(f"\n3. Comparison:")
    print(f"   Similarity: {comparison['similarity_score']:.2%}")
    print(f"   Differences: {len(comparison['differences'])}")
    
    return strategy


def example_4_batch_processing():
    """Example 4: Process multiple directories."""
    print("\n" + "=" * 60)
    print("EXAMPLE 4: Batch Processing Multiple Directories")
    print("=" * 60)
    
    # Define directories to analyze
    directories = {
        "core": "../../planfile",
        "examples": "../strategies",
        "tests": "../../tests",
    }
    
    results = {}
    
    for name, path in directories.items():
        print(f"\n📁 Processing {name}: {path}")
        
        if Path(path).exists():
            try:
                # Generate strategy for each directory
                strategy = generator.generate_from_current_project(
                    project_path=path,
                    project_name=f"batch-{name}",
                    max_sprints=2
                )
                
                # Get statistics
                stats = strategy.get_stats() if hasattr(strategy, 'get_stats') else {}
                
                results[name] = {
                    'sprints': len(strategy.get('sprints', [])),
                    'tasks': stats.get('total_tasks', 0),
                    'quality_gates': len(strategy.get('quality_gates', []))
                }
                
                # Save individual strategy
                filename = f"batch-{name}-strategy.yaml"
                save_strategy_yaml(strategy, filename)
                print(f"  ✓ Saved: {filename}")
                
            except Exception as e:
                print(f"  ✗ Failed: {e}")
                results[name] = None
        else:
            print(f"  ⚠ Directory not found: {path}")
            results[name] = None
    
    # Summary table
    print("\n📊 Batch Processing Summary:")
    print(f"{'Directory':<15} {'Sprints':<10} {'Tasks':<10} {'Quality Gates':<15}")
    print("-" * 55)
    
    for name, result in results.items():
        if result:
            print(f"{name:<15} {result['sprints']:<10} {result['tasks']:<10} {result['quality_gates']:<15}")
        else:
            print(f"{name:<15} {'Failed':<10} {'-':<10} {'-':<15}")
    
    # Create combined strategy
    print("\n🔗 Creating combined strategy...")
    valid_strategies = []
    for name, path in directories.items():
        filename = f"batch-{name}-strategy.yaml"
    if len(valid_strategies) > 1:
        combined = valid_strategies[0].merge(
            valid_strategies[1:],
            name="Combined Batch Strategy"
        )
        
        save_strategy_yaml(combined, "batch-combined-strategy.yaml")
        print(f"  ✓ Combined strategy saved with {len(combined.sprints)} sprints")
    
    return results


def example_5_custom_metrics():
    """Example 5: Add custom metrics to analysis."""
    print("\n" + "=" * 60)
    print("EXAMPLE 5: Custom Metrics Integration")
    print("=" * 60)
    
    # Create custom analyzer
    analyzer = FileAnalyzer()
    
    # Add custom issue patterns
    import re
    from planfile.analysis.parsers.text_parser import ISSUE_PATTERNS
    ISSUE_PATTERNS.update({
        'security': re.compile(r'(?i)SECURITY\s*[:#]?\s*(.+)', re.MULTILINE),
        'performance': re.compile(r'(?i)PERFORMANCE\s*[:#]?\s*(.+)', re.MULTILINE),
        'api': re.compile(r'(?i)API\s*[:#]?\s*(.+)', re.MULTILINE),
    })
    
    # Analyze with custom patterns
    result = analyzer.analyze_directory(Path("../../planfile"))
    
    # Count custom issues
    custom_issues = {}
    for issue in result['issues']:
        category = issue.get('category', 'unknown')
        if category in ['security', 'performance', 'api']:
            custom_issues[category] = custom_issues.get(category, 0) + 1
    
    print("Custom Issues Found:")
    for category, count in custom_issues.items():
        print(f"  {category}: {count}")
    
    # Generate strategy with custom metrics
    strategy = generator.generate_from_analysis(
        analysis_path="../../planfile",
        project_name="custom-metrics-example",
        max_sprints=3,
        external_metrics={
            'custom_security_issues': custom_issues.get('security', 0),
            'custom_performance_issues': custom_issues.get('performance', 0),
            'custom_api_issues': custom_issues.get('api', 0),
        }
    )
    
    # Add custom quality gates based on findings
    if custom_issues.get('security', 0) > 0:
        from planfile.models_v2 import QualityGate
        strategy['quality_gates'].append(
            QualityGate(
                name="Security Issues",
                description="All security issues must be resolved",
                criteria=["security_issues = 0"],
                required=True
            )
        )
    
    save_strategy_yaml(strategy, "custom-metrics-strategy.yaml")
    print(f"\n✓ Custom metrics strategy saved")
    
    return custom_issues


def example_6_workflow_automation():
    """Example 6: Automated workflow for CI/CD."""
    print("\n" + "=" * 60)
    print("EXAMPLE 6: CI/CD Workflow Automation")
    print("=" * 60)
    
    # Simulate CI/CD workflow
    workflow_steps = [
        ("1. Analyze Code", lambda: generator.generate_from_current_project(
            "../../planfile", "ci-analysis", max_sprints=2, focus_area="quality"
        )),
        ("2. Check Quality Gates", lambda: load_strategy_yaml("ci-analysis-strategy.yaml")),
        ("3. Generate Report", lambda: None),
        ("4. Create Tasks", lambda: None),
    ]
    
    artifacts = []
    
    for step_name, step_func in workflow_steps:
        print(f"\n{step_name}...")
        
        try:
            result = step_func()
            
            if result and hasattr(result, 'get'):
                # Save analysis result
                filename = f"ci-{step_name.lower().split()[1]}.yaml"
                save_strategy_yaml(result, filename)
                artifacts.append(filename)
                print(f"  ✓ Artifact: {filename}")
                
                # Check quality gates
                if 'quality_gates' in result:
                    gates = result['quality_gates']
                    critical_gates = [g for g in gates if g.get('required', False)]
                    print(f"  ✓ Quality Gates: {len(gates)} total, {len(critical_gates)} critical")
            
            elif result and hasattr(result, 'quality_gates'):
                # Strategy object
                print(f"  ✓ Quality Gates: {len(result.quality_gates)}")
                
                # Check if any critical gates would fail
                critical_count = sum(1 for g in result.quality_gates if g.required)
                print(f"  ✓ Critical requirements: {critical_count}")
            
            else:
                print(f"  ✓ Step completed")
                
        except Exception as e:
            print(f"  ✗ Failed: {e}")
    
    # Generate workflow summary
    print("\n📋 Workflow Summary:")
    print(f"  Artifacts created: {len(artifacts)}")
    for artifact in artifacts:
        if Path(artifact).exists():
            print(f"    ✓ {artifact}")
    
    # Create workflow script
    workflow_script = """#!/bin/bash
# CI/CD Planfile Workflow

echo "Running planfile analysis..."
python3 -m planfile.cli.commands generate-from-files . --focus quality --output ci-strategy.yaml

echo "Validating strategy..."
python3 -m planfile.cli.commands validate ci-strategy.yaml

echo "Checking project health..."
python3 -m planfile.cli.commands health . --output ci-health.json

echo "Exporting report..."
python3 -m planfile.cli.commands export ci-strategy.yaml --format html --output ci-report.html

echo "Workflow complete!"
"""
    
    with open("ci-workflow.sh", "w") as f:
        f.write(workflow_script)
    
    import os
    os.chmod("ci-workflow.sh", 0o755)
    print(f"\n✓ CI/CD workflow script created: ci-workflow.sh")
    
    return artifacts


def main():
    """Run all advanced examples."""
    print("\n" + "🚀" * 20)
    print("ADVANCED PLANFILE USAGE EXAMPLES")
    print("🚀" * 20)
    
    examples = [
        ("Custom File Patterns", example_1_custom_file_patterns),
        ("Focus Area Strategies", example_2_focus_area_strategies),
        ("Iterative Refinement", example_3_iterative_refinement),
        ("Batch Processing", example_4_batch_processing),
        ("Custom Metrics", example_5_custom_metrics),
        ("Workflow Automation", example_6_workflow_automation),
    ]
    
    results = {}
    
    for name, func in examples:
        try:
            print(f"\n📍 Running: {name}")
            result = func()
            results[name] = result
            print(f"✅ Completed: {name}")
        except Exception as e:
            print(f"❌ Failed: {name} - {e}")
            import traceback
            traceback.print_exc()
            results[name] = None
    
    # Summary
    print("\n" + "=" * 60)
    print("ADVANCED EXAMPLES SUMMARY")
    print("=" * 60)
    
    for name, result in results.items():
        status = "✅ Success" if result is not None else "❌ Failed"
        print(f"{name}: {status}")
    
    # List all generated files
    print("\n📁 Generated Files:")
    generated_files = [
        "custom-patterns-strategy.yaml",
        "focus-quality-strategy.yaml",
        "focus-security-strategy.yaml",
        "focus-performance-strategy.yaml",
        "focus-testing-strategy.yaml",
        "focus-documentation-strategy.yaml",
        "iterative-v1.yaml",
        "iterative-v2.yaml",
        "batch-core-strategy.yaml",
        "batch-examples-strategy.yaml",
        "batch-tests-strategy.yaml",
        "batch-combined-strategy.yaml",
        "custom-metrics-strategy.yaml",
        "ci-analysis-strategy.yaml",
        "ci-workflow.sh",
    ]
    
    for file in generated_files:
        if Path(file).exists():
            size = Path(file).stat().st_size
            print(f"  ✓ {file} ({size} bytes)")
    
    print("\n" + "🎉" * 20)
    print("ALL ADVANCED EXAMPLES COMPLETED!")
    print("🎉" * 20)
    
    print("\n💡 Tips:")
    print("  - Combine examples for more complex workflows")
    print("  - Use custom patterns for specific file types")
    print("  - Iterate on strategies to refine them")
    print("  - Batch process multiple directories")
    print("  - Add custom metrics for domain-specific needs")
    print("  - Automate workflows in CI/CD pipelines")


if __name__ == "__main__":
    main()
