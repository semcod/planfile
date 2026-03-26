#!/usr/bin/env python3
"""
Practical Planfile Example
Shows real usage with a working strategy file.
"""

import subprocess
import sys
import yaml
from pathlib import Path


def show_strategy_content(strategy_file):
    """Display key parts of a strategy file."""
    print(f"\n📄 Strategy: {strategy_file}")
    print("-" * 60)
    
    with open(strategy_file, 'r') as f:
        content = yaml.safe_load(f)
    
    print(f"Name: {content.get('name', 'N/A')}")
    print(f"Project: {content.get('project_name', 'N/A')}")
    print(f"Goal: {content.get('goal', 'N/A')}")
    
    print(f"\nSprints: {len(content.get('sprints', []))}")
    for sprint in content.get('sprints', [])[:3]:
        print(f"  - {sprint.get('name', 'N/A')} ({sprint.get('duration', 'N/A')})")
    
    print(f"\nQuality Gates: {len(content.get('quality_gates', []))}")
    for gate in content.get('quality_gates', [])[:3]:
        print(f"  - {gate.get('name', 'N/A')}: {gate.get('criteria', ['N/A'])[0] if gate.get('criteria') else 'N/A'}")


def run_planfile_command(cmd, description):
    """Run a planfile command and capture output."""
    print(f"\n{'='*60}")
    print(f"🔧 {description}")
    print(f"{'='*60}")
    
    full_cmd = [sys.executable, "-m", "planfile.cli.commands"] + cmd
    
    print(f"Command: {' '.join(full_cmd)}")
    print("-" * 60)
    
    try:
        # Use a simpler approach to avoid validation issues
        result = subprocess.run(
            full_cmd,
            capture_output=True,
            text=True,
            timeout=30,
            env={**dict(os.environ), "PYTHONPATH": "."}
        )
        
        print("STDOUT:")
        print(result.stdout or "(empty)")
        
        if result.stderr:
            print("\nSTDERR:")
            print(result.stderr)
        
        print(f"\nExit Code: {result.returncode}")
        
        return result.returncode == 0
        
    except Exception as e:
        print(f"Error running command: {e}")
        return False


def main():
    """Show practical planfile usage."""
    import os
    
    print("=" * 60)
    print("PRACTICAL PLANFILE USAGE EXAMPLE")
    print("=" * 60)
    
    # Use a working example strategy
    strategy_file = "examples/strategies/ecommerce-mvp.yaml"
    
    if not Path(strategy_file).exists():
        print(f"❌ Strategy file not found: {strategy_file}")
        return
    
    # 1. Show strategy content
    show_strategy_content(strategy_file)
    
    # 2. Validate strategy
    print(f"\n🔍 Validating Strategy...")
    success = run_planfile_command(
        ["validate", strategy_file],
        f"Validating {strategy_file}"
    )
    
    if success:
        print("✅ Strategy is valid!")
    else:
        print("⚠️  Strategy has issues (but we'll continue for demo)")
    
    # 3. Apply strategy (dry run)
    print(f"\n🎯 Applying Strategy (Dry Run)...")
    success = run_planfile_command(
        ["apply", strategy_file, ".", "--backend", "generic", "--dry-run"],
        "Applying strategy (dry run)"
    )
    
    # 4. Show what would happen
    print(f"\n📋 What Happens When Applying a Strategy:")
    print("-" * 60)
    print("1. Strategy is loaded and validated")
    print("2. Backend is initialized (GitHub, Jira, etc.)")
    print("3. For each sprint:")
    print("   - Task patterns are processed")
    print("   - Tickets are created with:")
    print("     * Title and description")
    print("     * Priority and labels")
    print("     * Assignee (if specified)")
    print("     * Due dates based on sprint duration")
    print("4. Progress tracking is set up")
    print("5. Reports are generated")
    
    # 5. Show example ticket creation
    print(f"\n🎫 Example Ticket Creation:")
    print("-" * 60)
    print("""
Ticket: Implement User Authentication
- Sprint: Sprint 1 (Foundation)
- Type: Feature
- Priority: High
- Description: Implement secure user authentication...
- Assignee: dev-team
- Labels: [feature, security, sprint-1]
- Story Points: 5
    """)
    
    # 6. Review command
    print(f"\n📊 Review Command Example:")
    print("-" * 60)
    print("Command: planfile review ecommerce-mvp.yaml . --backend github")
    print("\nThis would show:")
    print("- Sprint completion percentage")
    print("- Tickets by status (Todo, In Progress, Done)")
    print("- Quality gate metrics")
    print("- Burn-down chart data")
    print("- Blockers and risks")
    
    # 7. Integration examples
    print(f"\n🔗 Real-World Integrations:")
    print("-" * 60)
    
    print("\nGitHub Actions Workflow:")
    print("""
name: Planfile Strategy
on:
  push:
    branches: [main]

jobs:
  apply-strategy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Apply Planfile Strategy
        run: |
          python3 -m planfile.cli.commands apply \
            strategy.yaml . \
            --backend github \
            --token ${{ secrets.GITHUB_TOKEN }}
    """)
    
    print("\nJenkins Pipeline:")
    print("""
pipeline {
    agent any
    stages {
        stage('Apply Strategy') {
            steps {
                sh 'python3 -m planfile.cli.commands apply strategy.yaml . --backend jira'
            }
        }
    }
}
    """)
    
    # 8. Best practices
    print(f"\n💡 Best Practices:")
    print("-" * 60)
    print("1. Always validate strategies before applying")
    print("2. Use --dry-run to preview changes")
    print("3. Customize templates for your team's workflow")
    print("4. Review auto-generated tickets")
    print("5. Use consistent naming conventions")
    print("6. Link tickets to documentation")
    print("7. Track metrics over time")
    print("8. Iterate and improve strategies")
    
    print("\n" + "=" * 60)
    print("✅ EXAMPLE COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
