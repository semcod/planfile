#!/usr/bin/env python3
"""
Simple Working Planfile Example
Demonstrates basic usage with minimal dependencies.
"""

import os
import sys
import subprocess
from pathlib import Path


def run_simple_command(cmd, cwd=None):
    """Run a simple command and return output."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd or ".",
            timeout=10
        )
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)


def main():
    """Show simple planfile usage."""
    print("=" * 60)
    print("SIMPLE PLANFILE USAGE EXAMPLE")
    print("=" * 60)
    
    # 1. List available strategies
    print("\n📁 Available Strategy Files:")
    print("-" * 40)
    
    strategies = list(Path(".").glob("examples/strategies/*.yaml"))
    for i, strategy in enumerate(strategies[:5], 1):
        print(f"{i}. {strategy.name}")
    
    if not strategies:
        print("No strategy files found in examples/strategies/")
        return
    
    # Use first strategy for demo
    demo_strategy = strategies[0]
    print(f"\nUsing: {demo_strategy.name}")
    
    # 2. Show strategy structure
    print(f"\n📄 Strategy Structure:")
    print("-" * 40)
    
    success, output, _ = run_simple_command(f"head -30 {demo_strategy}")
    if success:
        print(output)
    
    # 3. Validation command
    print(f"\n🔍 Validation Command:")
    print("-" * 40)
    print("python3 -m planfile.cli.commands validate strategy.yaml")
    print("\nWhat it does:")
    print("- Checks YAML syntax")
    print("- Validates required fields")
    print("- Verifies sprint structure")
    print("- Checks quality gate format")
    
    # 4. Apply command
    print(f"\n🎯 Apply Command:")
    print("-" * 40)
    print("python3 -m planfile.cli.commands apply strategy.yaml . --backend generic --dry-run")
    print("\nWhat it does:")
    print("- Loads strategy from YAML")
    print("- Creates tickets for each task pattern")
    print("- Organizes by sprints")
    print("- Outputs ticket details")
    print("(Dry run = no actual tickets created)")
    
    # 5. Review command
    print(f"\n📊 Review Command:")
    print("-" * 40)
    print("python3 -m planfile.cli.commands review strategy.yaml . --backend generic")
    print("\nWhat it does:")
    print("- Checks ticket status")
    print("- Calculates sprint progress")
    print("- Shows quality gate metrics")
    print("- Generates summary report")
    
    # 6. Example workflow
    print(f"\n🔄 Example Workflow:")
    print("-" * 40)
    print("""
# 1. Create or generate a strategy
python3 generate_from_files.py ./project

# 2. Validate the strategy
python3 -m planfile.cli.commands validate planfile-from-files.yaml

# 3. Preview what will be created
python3 -m planfile.cli.commands apply planfile-from-files.yaml . --backend generic --dry-run

# 4. Apply to real backend
python3 -m planfile.cli.commands apply planfile-from-files.yaml . --backend github

# 5. Track progress
python3 -m planfile.cli.commands review planfile-from-files.yaml .
    """)
    
    # 7. Backend options
    print(f"\n🔗 Backend Options:")
    print("-" * 40)
    print("""
--backend generic    # Output to console (good for testing)
--backend github     # Create GitHub issues
--backend jira       # Create Jira tickets (needs config)
--backend gitlab     # Create GitLab issues
    """)
    
    # 8. Common options
    print(f"\n⚙️ Common Options:")
    print("-" * 40)
    print("""
--dry-run          # Preview without creating tickets
--config FILE      # Backend configuration file
--sprint 1,2       # Process only specific sprints
--output FILE      # Save results to file
--verbose          # Show detailed output
    """)
    
    # 9. Real example output
    print(f"\n📋 Example Output (Dry Run):")
    print("-" * 40)
    print("""
Applying strategy: E-commerce MVP
Backend: generic (dry run)

Sprint 1: Product Catalog & Search
==================================
✓ Created ticket: Design database schema
✓ Created ticket: Implement product model
✓ Created ticket: Build search API
✓ Created ticket: Add product listing page

Sprint 2: Shopping Cart & Checkout
==================================
✓ Created ticket: Implement cart functionality
✓ Created ticket: Build checkout flow
✓ Created ticket: Integrate payment gateway

Summary:
- Total tickets: 7
- Sprints: 3
- Estimated effort: 3 weeks
    """)
    
    # 10. Tips
    print(f"\n💡 Quick Tips:")
    print("-" * 40)
    print("• Always use --dry-run first")
    print("• Check strategy with validate before applying")
    print("• Use generic backend for testing")
    print("• Custom strategy templates in examples/strategies/")
    print("• Combine with CI/CD for automation")
    
    print("\n" + "=" * 60)
    print("✅ DONE! Try running the commands above.")
    print("=" * 60)


if __name__ == "__main__":
    main()
