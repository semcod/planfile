#!/usr/bin/env python3
"""
Comprehensive example demonstrating planfile usage with various strategies.
"""

import os
import sys
import subprocess
from pathlib import Path

def run_command(cmd, description):
    """Run a command and display results."""
    print(f"\n{'='*60}")
    print(f"🚀 {description}")
    print(f"{'='*60}")
    
    print(f"Command: {' '.join(cmd)}")
    print("-" * 60)
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.stdout:
            print(result.stdout)
        
        if result.stderr:
            print("STDERR:", result.stderr)
        
        if result.returncode == 0:
            print(f"\n✅ Success!")
        else:
            print(f"\n❌ Failed with exit code {result.returncode}")
        
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print(f"\n⏰ Command timed out after 60 seconds")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False

def main():
    """Run comprehensive examples."""
    print("=" * 60)
    print("PLANFILE COMPREHENSIVE EXAMPLES")
    print("=" * 60)
    
    strategies_dir = Path("planfile/examples/strategies")
    
    # Example 1: Validate all strategies
    print("\n\n📋 EXAMPLE 1: Validate All Strategies")
    for strategy_file in sorted(strategies_dir.glob("*.yaml")):
        cmd = [sys.executable, "-m", "planfile.cli.commands", "validate", str(strategy_file)]
        run_command(cmd, f"Validating {strategy_file.name}")
    
    # Example 2: Generate a new strategy
    print("\n\n📝 EXAMPLE 2: Generate a New Strategy")
    cmd = [
        sys.executable, "-m", "planfile.cli.commands", "generate",
        "--project-path", ".",
        "--model", "anthropic/claude-sonnet-4",
        "--sprints", "3",
        "--focus", "quality",
        "--dry-run"
    ]
    run_command(cmd, "Generating new strategy (dry run)")
    
    # Example 3: Apply a strategy (dry run)
    print("\n\n🎯 EXAMPLE 3: Apply Strategy (Dry Run)")
    strategy_file = strategies_dir / "microservices-migration.yaml"
    cmd = [
        sys.executable, "-m", "planfile.cli.commands", "apply",
        str(strategy_file),
        ".",
        "--backend", "generic",
        "--dry-run",
        "--verbose"
    ]
    run_command(cmd, f"Applying {strategy_file.name} (dry run)")
    
    # Example 4: Review strategy progress
    print("\n\n📊 EXAMPLE 4: Review Strategy Progress")
    cmd = [
        sys.executable, "-m", "planfile.cli.commands", "review",
        str(strategy_file),
        ".",
        "--backend", "generic",
        "--output", "review-results.json"
    ]
    run_command(cmd, f"Reviewing {strategy_file.name}")
    
    # Example 5: Export results to markdown
    if Path("review-results.json").exists():
        print("\n\n📄 EXAMPLE 5: Export Results to Markdown")
        cmd = [
            sys.executable, "-c",
            f"""
import json
from planfile.loaders.cli_loader import export_results_to_markdown

with open('review-results.json', 'r') as f:
    results = json.load(f)

export_results_to_markdown(results, 'strategy-review.md')
print('✅ Results exported to strategy-review.md')
            """
        ]
        run_command(cmd, "Exporting results to markdown")
    
    # Example 6: Show strategy metrics
    print("\n\n📈 EXAMPLE 6: Analyze Project Metrics")
    cmd = [
        sys.executable, "-c",
        """
from planfile.utils.metrics import analyze_project_metrics
import json

metrics = analyze_project_metrics('.')
print('Project Metrics:')
print(json.dumps(metrics, indent=2))
        """
    ]
    run_command(cmd, "Analyzing project metrics")
    
    # Example 7: Generate strategy with LLM
    if os.environ.get("OPENROUTER_API_KEY"):
        print("\n\n🤖 EXAMPLE 7: Generate Strategy with LLM")
        cmd = [
            sys.executable, "-m", "planfile.cli.commands", "generate",
            "--project-path", ".",
            "--model", "anthropic/claude-sonnet-4",
            "--sprints", "2",
            "--focus", "performance",
            "--output", "llm-strategy.yaml"
        ]
        run_command(cmd, "Generating strategy with LLM")
    else:
        print("\n\n⚠️  EXAMPLE 7: Skipped (OPENROUTER_API_KEY not set)")
    
    print("\n\n" + "=" * 60)
    print("✅ ALL EXAMPLES COMPLETED")
    print("=" * 60)
    print("\nGenerated files:")
    for file in ["llm-strategy.yaml", "strategy-review.md", "review-results.json"]:
        if Path(file).exists():
            print(f"  - {file}")
    
    print("\nNext steps:")
    print("1. Examine the generated strategies in planfile/examples/strategies/")
    print("2. Try applying a strategy with real backend configuration")
    print("3. Set up OPENROUTER_API_KEY to enable LLM generation")
    print("4. Check the documentation for more advanced features")

if __name__ == "__main__":
    main()
