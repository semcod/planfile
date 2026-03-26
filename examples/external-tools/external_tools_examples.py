#!/usr/bin/env python3
"""
Example demonstrating external tools integration.
Shows how to use code2llm, vallm, and redup with planfile.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from planfile.analysis.external_tools import ExternalToolRunner, AnalysisResults
from planfile.analysis.generator import generator
from planfile.loaders.yaml_loader import save_strategy_yaml


def example_1_check_external_tools():
    """Example 1: Check if external tools are available."""
    print("=" * 60)
    print("EXAMPLE 1: Check External Tools Availability")
    print("=" * 60)
    
    runner = ExternalToolRunner(Path("."))
    
    tools = {
        "code2llm": runner.has_code2llm,
        "vallm": runner.has_vallm,
        "redup": runner.has_redup
    }
    
    print("External Tools Status:")
    for tool, available in tools.items():
        status = "✓ Available" if available else "✗ Not Found"
        print(f"  {tool}: {status}")
    
    if all(tools.values()):
        print("\n✅ All external tools are available!")
        return True
    else:
        missing = [t for t, a in tools.items() if not a]
        print(f"\n⚠ Missing tools: {', '.join(missing)}")
        print("  Install missing tools with: pip install code2llm vallm redup")
        return False


def example_2_run_individual_tools():
    """Example 2: Run each tool individually."""
    print("\n" + "=" * 60)
    print("EXAMPLE 2: Run Individual Tools")
    print("=" * 60)
    
    runner = ExternalToolRunner(Path("../"))
    
    # Run code2llm
    if runner.has_code2llm:
        print("\n🔍 Running code2llm...")
        try:
            result = runner.run_code2llm()
            print(f"  ✓ Output: {result}")
            print(f"  ✓ File: {runner.output_dir / 'analysis.toon.yaml'}")
        except Exception as e:
            print(f"  ✗ Failed: {e}")
    
    # Run vallm
    if runner.has_vallm:
        print("\n🔍 Running vallm...")
        try:
            result = runner.run_vallm()
            print(f"  ✓ Output: {result}")
            print(f"  ✓ File: {runner.output_dir / 'validation.toon.yaml'}")
        except Exception as e:
            print(f"  ✗ Failed: {e}")
    
    # Run redup
    if runner.has_redup:
        print("\n🔍 Running redup...")
        try:
            result = runner.run_redup()
            print(f"  ✓ Output: {result}")
            print(f"  ✓ File: {runner.output_dir / 'duplication.toon.yaml'}")
        except Exception as e:
            print(f"  ✗ Failed: {e}")


def example_3_run_all_tools():
    """Example 3: Run all tools and get results."""
    print("\n" + "=" * 60)
    print("EXAMPLE 3: Run All Tools")
    print("=" * 60)
    
    runner = ExternalToolRunner(Path("../"))
    
    # Run all tools
    results = runner.run_all()
    
    # Display results
    print("\n📊 Analysis Results:")
    print(f"  Average CC: {results.cc_average:.2f}")
    print(f"  Critical Functions: {results.critical_functions}")
    print(f"  High CC Functions: {len(results.high_cc_functions)}")
    print(f"  Validation Errors: {results.validation_errors}")
    print(f"  Validation Warnings: {results.validation_warnings}")
    print(f"  Duplication Groups: {results.duplication_groups}")
    print(f"  Lines Saved by Deduplication: {results.saved_lines}")
    print(f"  Pass Rate: {results.pass_rate:.2%}")
    
    # Show high CC functions
    if results.high_cc_functions:
        print("\n⚠ High CC Functions:")
        for func in results.high_cc_functions[:5]:  # Show top 5
            print(f"  • {func['name']}: CC={func['cc']} in {func['file']}")
    
    return results


def example_4_generate_strategy_with_tools():
    """Example 4: Generate strategy using external tools."""
    print("\n" + "=" * 60)
    print("EXAMPLE 4: Generate Strategy with External Tools")
    print("=" * 60)
    
    try:
        strategy = generator.generate_with_external_tools(
            project_path="../",
            project_name="planfile-self-analysis",
            max_sprints=4,
            focus_area="quality"
        )
        
        print(f"\n✓ Strategy Generated!")
        print(f"  Name: {strategy.get('name', 'N/A')}")
        print(f"  Sprints: {len(strategy.get('sprints', []))}")
        
        # Show sprints
        print("\n📋 Generated Sprints:")
        for i, sprint in enumerate(strategy.get('sprints', [])[:3], 1):
            print(f"\n  Sprint {i}: {sprint.get('name', 'N/A')}")
            print(f"    Duration: {sprint.get('duration', 'N/A')}")
            objectives = sprint.get('objectives', [])
            if objectives:
                print("    Objectives:")
                for obj in objectives[:3]:
                    print(f"      • {obj}")
        
        # Save strategy
        output_file = "external-tools-generated.yaml"
        save_strategy_yaml(strategy, output_file)
        print(f"\n✓ Strategy saved to: {output_file}")
        
        return strategy
        
    except Exception as e:
        print(f"\n✗ Failed to generate strategy: {e}")
        print("  This might be due to missing external tools")
        return None


def example_5_custom_analysis():
    """Example 5: Custom analysis with specific focus."""
    print("\n" + "=" * 60)
    print("EXAMPLE 5: Custom Analysis with Focus")
    print("=" * 60)
    
    # Create custom runner with specific output directory
    output_dir = Path("./custom_analysis")
    output_dir.mkdir(exist_ok=True)
    
    runner = ExternalToolRunner(Path("../"), output_dir=output_dir)
    
    # Run analysis
    results = runner.run_all()
    
    # Focus on specific metrics
    print("\n🎯 Quality Focus Analysis:")
    
    if results.cc_average > 4:
        print(f"  ⚠ High average CC: {results.cc_average:.2f} (>4)")
        print("    Recommendation: Refactor complex functions")
    
    if results.critical_functions > 0:
        print(f"  ⚠ Critical functions: {results.critical_functions}")
        print("    Recommendation: Immediate refactoring required")
    
    if results.validation_errors > 0:
        print(f"  ⚠ Validation errors: {results.validation_errors}")
        print("    Recommendation: Fix all errors before proceeding")
    
    if results.duplication_groups > 0:
        print(f"  ⚠ Duplication groups: {results.duplication_groups}")
        print("    Recommendation: Extract common code")
    
    # Generate focused strategy
    try:
        strategy = generator.generate_with_external_tools(
            project_path="../",
            project_name="quality-focused",
            max_sprints=2,
            focus_area="quality"
        )
        
        # Show quality-focused sprints
        print("\n📋 Quality-Focused Sprints:")
        for sprint in strategy.get('sprints', []):
            print(f"\n  • {sprint.get('name')}")
            print(f"    Tasks: {len(sprint.get('task_patterns', []))}")
        
        save_strategy_yaml(strategy, "quality-focused.yaml")
        print("\n✓ Quality-focused strategy saved!")
        
    except Exception as e:
        print(f"\n✗ Failed: {e}")


def main():
    """Run all external tools examples."""
    print("\n" + "🔧" * 20)
    print("EXTERNAL TOOLS INTEGRATION EXAMPLES")
    print("🔧" * 20)
    
    # Check if tools are available
    tools_available = example_1_check_external_tools()
    
    if not tools_available:
        print("\n⚠ Some external tools are not available.")
        print("  Install with: pip install code2llm vallm redup")
        print("  Running examples with available tools...\n")
    
    # Run examples
    examples = [
        ("Run Individual Tools", example_2_run_individual_tools),
        ("Run All Tools", example_3_run_all_tools),
        ("Generate Strategy", example_4_generate_strategy_with_tools),
        ("Custom Analysis", example_5_custom_analysis),
    ]
    
    results = {}
    
    for name, func in examples:
        try:
            print(f"\n📍 Running: {name}")
            result = func()
            results[name] = result
        except Exception as e:
            print(f"❌ Failed: {name} - {e}")
            results[name] = None
    
    # Summary
    print("\n" + "=" * 60)
    print("EXTERNAL TOOLS SUMMARY")
    print("=" * 60)
    
    if results.get("Run All Tools"):
        results_obj = results["Run All Tools"]
        print(f"Analysis Results:")
        print(f"  Files analyzed: {len(list(Path('../').rglob('*.py')))}")
        print(f"  Average CC: {results_obj.cc_average:.2f}")
        print(f"  Issues found: {results_obj.validation_errors + results_obj.validation_warnings}")
        print(f"  Duplication: {results_obj.duplication_groups} groups")
    
    print("\nGenerated Files:")
    generated_files = [
        "external-tools-generated.yaml",
        "quality-focused.yaml"
    ]
    
    for file in generated_files:
        if Path(file).exists():
            print(f"  ✓ {file}")
    
    print("\n" + "🎉" * 20)
    print("EXTERNAL TOOLS EXAMPLES COMPLETED!")
    print("🎉" * 20)


if __name__ == "__main__":
    main()
