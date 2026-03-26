#!/usr/bin/env python3
"""
Examples demonstrating the new CLI commands.
Run this script to see example command usages.
"""

import subprocess
import sys
from pathlib import Path

def run_command(cmd, description, check=True):
    """Run a command and display results."""
    print(f"\n{'='*60}")
    print(f"🚀 {description}")
    print(f"{'='*60}")
    
    print(f"Command: {' '.join(cmd)}")
    print("-" * 60)
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.stdout:
            print(result.stdout)
        
        if result.stderr:
            print("STDERR:", result.stderr)
        
        if result.returncode == 0:
            print(f"\n✅ Success!")
        else:
            print(f"\n❌ Failed with exit code {result.returncode}")
            if check:
                sys.exit(1)
        
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print(f"\n⏰ Command timed out")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


def main():
    """Demonstrate CLI commands."""
    print("=" * 60)
    print("PLANFILE CLI COMMAND EXAMPLES")
    print("=" * 60)
    
    # Change to examples directory
    examples_dir = Path(__file__).parent
    import os
    os.chdir(examples_dir)
    
    # Example 1: Generate template
    run_command([
        sys.executable, "-m", "planfile.cli.commands",
        "template", "web", "ecommerce",
        "--output", "cli-example-web.yaml"
    ], "Generate Web Template")
    
    # Example 2: Show stats
    run_command([
        sys.executable, "-m", "planfile.cli.commands",
        "stats", "cli-example-web.yaml"
    ], "Show Strategy Statistics")
    
    # Example 3: Export to different formats
    formats = [
        ("yaml", "cli-example-web-export.yaml"),
        ("json", "cli-example-web-export.json"),
        ("html", "cli-example-web.html")
    ]
    
    for fmt, output in formats:
        run_command([
            sys.executable, "-m", "planfile.cli.commands",
            "export", "cli-example-web.yaml",
            "--format", fmt,
            "--output", output
        ], f"Export to {fmt.upper()}")
    
    # Example 4: Generate another template for comparison
    run_command([
        sys.executable, "-m", "planfile.cli.commands",
        "template", "mobile", "healthcare",
        "--output", "cli-example-mobile.yaml"
    ], "Generate Mobile Template")
    
    # Example 5: Compare strategies
    run_command([
        sys.executable, "-m", "planfile.cli.commands",
        "compare", "cli-example-web.yaml", "cli-example-mobile.yaml"
    ], "Compare Two Strategies")
    
    # Example 6: Validate strategies
    for strategy in ["cli-example-web.yaml", "cli-example-mobile.yaml"]:
        run_command([
            sys.executable, "-m", "planfile.cli.commands",
            "validate", strategy
        ], f"Validate {strategy}")
    
    # Example 7: Generate from files
    run_command([
        sys.executable, "-m", "planfile.cli.commands",
        "generate-from-files", "./strategies",
        "--output", "cli-generated-from-files.yaml",
        "--project-name", "strategies-analysis",
        "--max-sprints", "2"
    ], "Generate Strategy from Files", check=False)
    
    # Example 8: Health check
    run_command([
        sys.executable, "-m", "planfile.cli.commands",
        "health", "./strategies"
    ], "Check Project Health", check=False)
    
    # Example 9: Show help for new commands
    new_commands = ["export", "compare", "template", "stats", "health", "generate-from-files"]
    
    print("\n" + "=" * 60)
    print("NEW COMMANDS HELP")
    print("=" * 60)
    
    for cmd in new_commands:
        run_command([
            sys.executable, "-m", "planfile.cli.commands",
            cmd, "--help"
        ], f"Help for '{cmd}' command", check=False)
    
    # Summary
    print("\n" + "=" * 60)
    print("FILES GENERATED")
    print("=" * 60)
    
    generated_files = [
        "cli-example-web.yaml",
        "cli-example-mobile.yaml",
        "cli-example-web-export.yaml",
        "cli-example-web-export.json",
        "cli-example-web.html",
        "cli-generated-from-files.yaml"
    ]
    
    for file in generated_files:
        if Path(file).exists():
            print(f"  ✓ {file}")
    
    print("\n" + "=" * 60)
    print("COMMANDS SUMMARY")
    print("=" * 60)
    
    commands_summary = """
    NEW CLI COMMANDS:
    
    1. planfile template <type> <domain>
       Generate strategy templates for different project types
       Types: web, mobile, ml
       Example: planfile template web ecommerce
    
    2. planfile stats <strategy.yaml>
       Show statistics about a strategy
       Example: planfile stats my-strategy.yaml
    
    3. planfile export <strategy.yaml> --format <fmt>
       Export strategy to different formats
       Formats: yaml, json, csv, html, markdown
       Example: planfile export strategy.yaml --format html
    
    4. planfile compare <strategy1.yaml> <strategy2.yaml>
       Compare two strategies and show differences
       Example: planfile compare old.yaml new.yaml
    
    5. planfile health <path>
       Check project health and suggest improvements
       Example: planfile health .
    
    6. planfile generate-from-files <path>
       Generate strategy from file analysis (no LLM needed)
       Example: planfile generate-from-files . --focus quality
    
    All commands support --help for more options.
    """
    
    print(commands_summary)
    
    print("\n🎉 All CLI examples completed!")


if __name__ == "__main__":
    main()
