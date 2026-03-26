#!/usr/bin/env python3
"""
Demonstration of Planfile Usage with Current Project
Shows how to use planfile CLI commands effectively.
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd, description):
    """Run a command and display results."""
    print(f"\n{'='*60}")
    print(f"🔧 {description}")
    print(f"{'='*60}")
    print(f"Command: {' '.join(cmd)}")
    print("-" * 60)
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.stdout:
            print(result.stdout)
        
        if result.stderr:
            print("STDERR:", result.stderr[:500])
        
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print("⏰ Command timed out")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    """Demonstrate planfile usage."""
    print("=" * 60)
    print("PLANFILE USAGE DEMONSTRATION")
    print("=" * 60)
    
    # 1. Show available commands
    print("\n📋 Available Planfile Commands:")
    print("-" * 40)
    print("1. validate  - Validate strategy YAML file")
    print("2. generate  - Generate strategy from analysis")
    print("3. apply     - Apply strategy to create tickets")
    print("4. review    - Review strategy progress")
    print("5. auto      - Automated CI/CD commands")
    
    # 2. List available strategy files
    print("\n📁 Available Strategy Files:")
    print("-" * 40)
    strategies = list(Path(".").glob("*.yaml"))
    for strategy in strategies:
        print(f"  - {strategy}")
    
    # 3. Validate a strategy file
    if strategies:
        strategy_file = strategies[0]
        print(f"\n✅ Validating {strategy_file}...")
        success = run_command([
            sys.executable, "-c", 
            f"""
import sys
sys.path.insert(0, '.')
from planfile.cli.commands import app
app(['validate', '{strategy_file}'])
            """
        ], f"Validating {strategy_file}")
        
        if success:
            print(f"✅ {strategy_file} is valid!")
        else:
            print(f"❌ {strategy_file} has validation issues")
    
    # 4. Generate a new strategy
    print("\n🏗️ Generating New Strategy...")
    print("-" * 40)
    print("Option 1: Generate from project analysis")
    print("  python3 -m planfile.cli.commands generate --project-path . --focus quality")
    print("\nOption 2: Use our automated generator")
    print("  python3 generate_from_files.py ./project")
    print("\nOption 3: Generate with LLM")
    print("  python3 -m planfile.cli.commands generate --model anthropic/claude-3-sonnet")
    
    # 5. Apply strategy (dry run)
    if strategies:
        print(f"\n🎯 Applying Strategy (Dry Run)...")
        print("-" * 40)
        print(f"Command: python3 -m planfile.cli.commands apply {strategies[0]} . --backend generic --dry-run")
        
        # Note: We'll show the command but not run it due to potential issues
        print("\nThis would:")
        print("  - Create tickets for each task pattern")
        print("  - Organize them by sprint")
        print("  - Generate reports")
        print("  - Track progress")
    
    # 6. Review strategy
    print("\n📊 Review Strategy Progress...")
    print("-" * 40)
    print(f"Command: python3 -m planfile.cli.commands review {strategies[0]} . --backend generic")
    print("\nThis would show:")
    print("  - Sprint completion status")
    print("  - Ticket progress")
    print("  - Quality gate metrics")
    print("  - Overall project health")
    
    # 7. Auto-loop feature
    print("\n🔄 Auto-Loop Feature...")
    print("-" * 40)
    print("Command: python3 -m planfile.cli.commands auto-loop strategy.yaml . --backend github")
    print("\nThis automated feature:")
    print("  - Runs tests")
    print("  - Creates tickets for failures")
    print("  - Attempts auto-fix with LLM")
    print("  - Repeats until all pass")
    
    # 8. Integration examples
    print("\n🔗 Integration Examples...")
    print("-" * 40)
    
    print("\nGitHub Integration:")
    print("  python3 -m planfile.cli.commands apply strategy.yaml . --backend github")
    print("  - Creates GitHub issues")
    print("  - Uses project milestones for sprints")
    print("  - Tracks progress with labels")
    
    print("\nJira Integration:")
    print("  python3 -m planfile.cli.commands apply strategy.yaml . --backend jira --config jira-config.yaml")
    print("  - Creates Jira tickets")
    print("  - Maps to existing workflow")
    print("  - Uses custom fields")
    
    print("\nGeneric Backend:")
    print("  python3 -m planfile.cli.commands apply strategy.yaml . --backend generic")
    print("  - Outputs to console/JSON")
    print("  - Good for testing and demos")
    
    # 9. Workflow example
    print("\n🔄 Typical Workflow...")
    print("-" * 40)
    print("1. Analyze project:")
    print("   python3 generate_from_files.py ./project")
    print("\n2. Review generated planfile:")
    print("   python3 -m planfile.cli.commands validate planfile-from-files.yaml")
    print("\n3. Apply to project management:")
    print("   python3 -m planfile.cli.commands apply planfile-from-files.yaml . --backend github")
    print("\n4. Track progress:")
    print("   python3 -m planfile.cli.commands review planfile-from-files.yaml .")
    print("\n5. Iterate after completion:")
    print("   Re-run analysis to measure improvements")
    
    # 10. Tips and best practices
    print("\n💡 Tips and Best Practices...")
    print("-" * 40)
    print("• Always validate before applying")
    print("• Use --dry-run to preview changes")
    print("• Customize strategy for your team's workflow")
    print("• Review generated tickets before creation")
    print("• Use quality gates to track improvements")
    print("• Combine with CI/CD for automated tracking")
    
    print("\n" + "=" * 60)
    print("✅ DEMONSTRATION COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
