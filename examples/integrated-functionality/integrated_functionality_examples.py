#!/usr/bin/env python3
"""
Examples demonstrating the new integrated planfile functionality.
Shows how to use file analysis, templates, exports, and comparisons.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from planfile.analysis.generator import generator
from planfile import Strategy
from planfile.loaders.yaml_loader import save_strategy_yaml


def example_1_generate_from_files():
    """Example 1: Generate strategy from file analysis."""
    print("=" * 60)
    print("EXAMPLE 1: Generate Strategy from File Analysis")
    print("=" * 60)
    
    # Generate from current examples directory
    strategy = generator.generate_from_current_project(
        project_path="./strategies",
        project_name="example-strategies",
        max_sprints=3,
        focus_area="quality"
    )
    
    print(f"✓ Generated strategy: {strategy.get('name', 'N/A')}")
    print(f"  Sprints: {len(strategy.get('sprints', []))}")
    print(f"  Quality gates: {len(strategy.get('quality_gates', []))}")
    
    # Save the strategy
    output_file = "generated-from-examples.yaml"
    save_strategy_yaml(strategy, output_file)
    print(f"✓ Saved to: {output_file}")
    
    return strategy


def example_2_template_generation():
    """Example 2: Generate strategy templates."""
    print("\n" + "=" * 60)
    print("EXAMPLE 2: Generate Strategy Templates")
    print("=" * 60)
    
    from planfile.cli.extra_commands import generate_template
    
    project_types = ['web', 'mobile', 'ml']
    domains = ['ecommerce', 'healthcare', 'finance']
    
    templates = []
    for i, (ptype, domain) in enumerate(zip(project_types, domains)):
        strategy = generate_template(ptype, domain)
        filename = f"template-{ptype}-{domain}.yaml"
        save_strategy_yaml(strategy, filename)
        
        print(f"\nTemplate {i+1}: {ptype} for {domain}")
        print(f"  File: {filename}")
        print(f"  Sprints: {len(strategy.sprints)}")
        print(f"  Quality gates: {len(strategy.quality_gates)}")
        
        templates.append((filename, strategy))
    
    return templates


def example_3_strategy_comparison():
    """Example 3: Compare strategies."""
    print("\n" + "=" * 60)
    print("EXAMPLE 3: Strategy Comparison")
    print("=" * 60)
    
    # Load two different templates
    template1 = Strategy.load("template-web-ecommerce.yaml")
    template2 = Strategy.load("template-mobile-healthcare.yaml")
    
    # Compare them
    comparison = template1.compare(template2)
    
    print(f"Comparing '{template1.name}' vs '{template2.name}'")
    print(f"Similarity Score: {comparison['similarity_score']:.2%}")
    
    print("\nCommon Elements:")
    for item in comparison['common_elements']:
        print(f"  ✓ {item}")
    
    print("\nDifferences:")
    for diff in comparison['differences']:
        if isinstance(diff, dict):
            print(f"  • {diff['field']}: '{diff['self']}' vs '{diff['other']}'")
        else:
            print(f"  • {diff}")
    
    return comparison


def example_4_export_formats():
    """Example 4: Export strategies to different formats."""
    print("\n" + "=" * 60)
    print("EXAMPLE 4: Export to Multiple Formats")
    print("=" * 60)
    
    # Load a strategy
    strategy = Strategy.load("template-web-ecommerce.yaml")
    
    # Export to different formats
    formats = {
        'yaml': 'strategy-export.yaml',
        'json': 'strategy-export.json',
        'dict': 'strategy-export-dict.txt'
    }
    
    for format_type, filename in formats.items():
        try:
            content = strategy.export(format_type)
            
            if format_type == 'dict':
                # For dict, just save the string representation
                with open(filename, 'w') as f:
                    f.write(str(content))
            else:
                with open(filename, 'w') as f:
                    f.write(content)
            
            print(f"✓ Exported to {filename}")
        except Exception as e:
            print(f"✗ Failed to export {format_type}: {e}")
    
    # Use CLI export for HTML and CSV
    print("\nUsing CLI export for additional formats:")
    print("  planfile export template-web-ecommerce.yaml --format html --output strategy.html")
    print("  planfile export template-web-ecommerce.yaml --format csv --output strategy.csv")
    
    return formats


def example_5_strategy_stats():
    """Example 5: Get strategy statistics."""
    print("\n" + "=" * 60)
    print("EXAMPLE 5: Strategy Statistics")
    print("=" * 60)
    
    # Load a strategy
    strategy = Strategy.load("template-web-ecommerce.yaml")
    
    # Get statistics
    stats = strategy.get_stats()
    
    print(f"Statistics for '{strategy.name}':")
    print(f"  Total Sprints: {stats['total_sprints']}")
    print(f"  Total Tasks: {stats['total_tasks']}")
    print(f"  Quality Gates: {stats['total_quality_gates']}")
    print(f"  Project Type: {stats['project_type']}")
    print(f"  Domain: {stats['domain']}")
    print(f"  Version: {stats['version']}")
    
    if 'task_types' in stats:
        print("\nTask Type Breakdown:")
        for task_type, count in stats['task_types'].items():
            print(f"  {task_type}: {count}")
    
    if 'total_duration_days' in stats:
        print(f"\nDuration: {stats['total_duration_days']} days total")
        if 'avg_duration_days' in stats:
            print(f"Average: {stats['avg_duration_days']:.1f} days per sprint")
    
    return stats


def example_6_merge_strategies():
    """Example 6: Merge multiple strategies."""
    print("\n" + "=" * 60)
    print("EXAMPLE 6: Merge Strategies")
    print("=" * 60)
    
    # Load multiple strategies
    strategies = [
        Strategy.load("template-web-ecommerce.yaml"),
        Strategy.load("template-mobile-healthcare.yaml"),
        Strategy.load("template-ml-finance.yaml")
    ]
    
    # Merge them
    merged = strategies[0].merge(
        strategies[1:],
        name="Merged Multi-Domain Strategy"
    )
    
    print(f"Merged strategy name: {merged.name}")
    print(f"Total sprints: {len(merged.sprints)}")
    print(f"Total quality gates: {len(merged.quality_gates)}")
    
    # Save merged strategy
    save_strategy_yaml(merged, "merged-strategy.yaml")
    print("✓ Saved merged strategy to: merged-strategy.yaml")
    
    return merged


def example_7_external_tools():
    """Example 7: Generate with external tools (if available)."""
    print("\n" + "=" * 60)
    print("EXAMPLE 7: Generate with External Tools")
    print("=" * 60)
    
    # Check if external tools are available
    try:
        strategy = generator.generate_with_external_tools(
            project_path="../",
            project_name="planfile-self-analysis",
            max_sprints=3,
            focus_area="quality"
        )
        
        print(f"✓ Generated strategy using external tools")
        print(f"  Name: {strategy.get('name', 'N/A')}")
        print(f"  Sprints: {len(strategy.get('sprints', []))}")
        
        # Save if successful
        save_strategy_yaml(strategy, "external-tools-strategy.yaml")
        print("✓ Saved to: external-tools-strategy.yaml")
        
    except Exception as e:
        print(f"⚠ External tools not available or failed: {e}")
        print("  This is normal if code2llm, vallm, or redup are not installed")
    
    return None


def main():
    """Run all examples."""
    print("\n" + "🚀" * 20)
    print("PLANFILE INTEGRATED FUNCTIONALITY EXAMPLES")
    print("🚀" * 20)
    
    examples = [
        ("Generate from Files", example_1_generate_from_files),
        ("Template Generation", example_2_template_generation),
        ("Strategy Comparison", example_3_strategy_comparison),
        ("Export Formats", example_4_export_formats),
        ("Strategy Statistics", example_5_strategy_stats),
        ("Merge Strategies", example_6_merge_strategies),
        ("External Tools", example_7_external_tools),
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
            results[name] = None
    
    # Summary
    print("\n" + "=" * 60)
    print("EXAMPLES SUMMARY")
    print("=" * 60)
    
    for name, result in results.items():
        status = "✅ Success" if result is not None else "❌ Failed"
        print(f"{name}: {status}")
    
    print("\nGenerated Files:")
    generated_files = [
        "generated-from-examples.yaml",
        "template-web-ecommerce.yaml",
        "template-mobile-healthcare.yaml", 
        "template-ml-finance.yaml",
        "strategy-export.yaml",
        "strategy-export.json",
        "strategy-export-dict.txt",
        "merged-strategy.yaml",
        "external-tools-strategy.yaml"
    ]
    
    for file in generated_files:
        if Path(file).exists():
            print(f"  ✓ {file}")
    
    print("\n" + "🎉" * 20)
    print("ALL EXAMPLES COMPLETED!")
    print("🎉" * 20)


if __name__ == "__main__":
    main()
