#!/usr/bin/env python3
"""
Quick start examples for planfile.
Simple examples to get started quickly.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import planfile components
from planfile import Strategy
from planfile.analysis.generator import generator


def quick_start_1():
    """Quick Start 1: Generate a strategy from current directory."""
    print("=" * 50)
    print("QUICK START 1: Generate from Files")
    print("=" * 50)
    
    # Generate strategy from current directory
    strategy = generator.generate_from_current_project(
        project_path="./strategies",
        project_name="quick-start",
        max_sprints=2
    )
    
    print(f"✓ Generated strategy!")
    print(f"  Name: {strategy.get('name', 'N/A')}")
    print(f"  Sprints: {len(strategy.get('sprints', []))}")
    
    # Save it
    from planfile.loaders.yaml_loader import save_strategy_yaml
    save_strategy_yaml(strategy, "quick-start.yaml")
    print(f"✓ Saved to: quick-start.yaml")
    
    return strategy


def quick_start_2():
    """Quick Start 2: Create a template."""
    print("\n" + "=" * 50)
    print("QUICK START 2: Create Template")
    print("=" * 50)
    
    # Import template generator
    from planfile.cli.extra_commands import generate_template
    
    # Generate a web template
    strategy = generate_template("web", "example")
    
    print(f"✓ Generated web template!")
    print(f"  Sprints: {len(strategy.sprints)}")
    print(f"  Quality gates: {len(strategy.quality_gates)}")
    
    # Save it
    from planfile.loaders.yaml_loader import save_strategy_yaml
    save_strategy_yaml(strategy, "web-template.yaml")
    print(f"✓ Saved to: web-template.yaml")
    
    return strategy


def quick_start_3():
    """Quick Start 3: Load and analyze a strategy."""
    print("\n" + "=" * 50)
    print("QUICK START 3: Load and Analyze")
    print("=" * 50)
    
    # Load the strategy we just created
    strategy = Strategy.load("web-template.yaml")
    
    print(f"✓ Loaded strategy: {strategy.name}")
    
    # Get statistics
    stats = strategy.get_stats()
    print(f"\n📊 Statistics:")
    print(f"  Sprints: {stats['total_sprints']}")
    print(f"  Tasks: {stats['total_tasks']}")
    print(f"  Quality Gates: {stats['total_quality_gates']}")
    
    # Show sprints
    print(f"\n📋 Sprints:")
    for i, sprint in enumerate(strategy.sprints, 1):
        print(f"  {i}. {sprint.name}")
        print(f"     Duration: {getattr(sprint, 'duration', 'N/A')}")
        print(f"     Objectives: {len(sprint.objectives)}")
    
    return strategy


def quick_start_4():
    """Quick Start 4: Export to different formats."""
    print("\n" + "=" * 50)
    print("QUICK START 4: Export Formats")
    print("=" * 50)
    
    # Load strategy
    strategy = Strategy.load("web-template.yaml")
    
    # Export to JSON
    json_data = strategy.export("json")
    with open("web-template.json", "w") as f:
        f.write(json_data)
    print(f"✓ Exported to JSON: web-template.json")
    
    # Export to dict (Python)
    dict_data = strategy.export("dict")
    print(f"✓ Exported to Python dict: {len(dict_data)} keys")
    
    # Show a preview
    print(f"\n📄 Preview (first 200 chars of JSON):")
    print(json_data[:200] + "...")


def quick_start_5():
    """Quick Start 5: Compare two strategies."""
    print("\n" + "=" * 50)
    print("QUICK START 5: Compare Strategies")
    print("=" * 50)
    
    # Load both strategies
    strategy1 = Strategy.load("quick-start.yaml")
    strategy2 = Strategy.load("web-template.yaml")
    
    # Compare them
    comparison = strategy1.compare(strategy2)
    
    print(f"Comparing '{strategy1.name}' vs '{strategy2.name}'")
    print(f"Similarity: {comparison['similarity_score']:.2%}")
    
    print(f"\nCommon elements:")
    for item in comparison['common_elements'][:3]:
        print(f"  ✓ {item}")
    
    print(f"\nDifferences:")
    for diff in comparison['differences'][:3]:
        if isinstance(diff, dict):
            print(f"  • {diff.get('field', 'unknown')}: different")
    
    return comparison


def main():
    """Run all quick start examples."""
    print("\n" + "⚡" * 20)
    print("PLANFILE QUICK START")
    print("⚡" * 20)
    
    print("\nThese examples will get you started with planfile in minutes!")
    
    # Run all examples
    examples = [
        ("Generate from Files", quick_start_1),
        ("Create Template", quick_start_2),
        ("Load and Analyze", quick_start_3),
        ("Export Formats", quick_start_4),
        ("Compare Strategies", quick_start_5),
    ]
    
    for name, func in examples:
        try:
            result = func()
            print(f"\n✅ {name} - Complete!")
        except Exception as e:
            print(f"\n❌ {name} - Failed: {e}")
            print("   This might be expected if files don't exist")
    
    # Summary
    print("\n" + "=" * 50)
    print("QUICK START SUMMARY")
    print("=" * 50)
    
    print("\nFiles created:")
    files = ["quick-start.yaml", "web-template.yaml", "web-template.json"]
    for file in files:
        if Path(file).exists():
            print(f"  ✓ {file}")
    
    print("\nNext steps:")
    print("  1. Open the YAML files to see the strategy structure")
    print("  2. Try: python3 -m planfile.cli.commands stats quick-start.yaml")
    print("  3. Try: python3 -m planfile.cli.commands export web-template.yaml --format html")
    print("  4. Try: python3 -m planfile.cli.commands template mobile fitness")
    
    print("\n" + "🎉" * 20)
    print("QUICK START COMPLETE!")
    print("🎉" * 20)


if __name__ == "__main__":
    main()
