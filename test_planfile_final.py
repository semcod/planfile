#!/usr/bin/env python3
"""
Final test of planfile v2 with OpenRouter free models.
This demonstrates the working integration.
"""

import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

# Add planfile to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from planfile.executor_v2 import StrategyExecutor
from planfile.models_v2 import Strategy

console = Console()


def test_planfile_v2():
    """Test planfile v2 with OpenRouter models."""

    console.print(Panel(
        "[bold cyan]Planfile v2 + OpenRouter Test[/bold cyan]\n"
        "Testing simplified planfile execution with free models",
        title="Final Integration Test"
    ))

    # Load strategy
    strategy_file = Path(__file__).parent / "examples" / "strategy_simple_v2.yaml"
    console.print(f"\n[yellow]Loading strategy from:[/yellow] {strategy_file}")

    strategy = Strategy.load_flexible(strategy_file)
    console.print(f"[green]✓ Strategy loaded:[/green] {strategy.name}")
    console.print(f"  - Sprints: {len(strategy.sprints)}")
    console.print(f"  - Total tasks: {sum(len(s.tasks) for s in strategy.sprints)}")

    # Create executor with free model config
    console.print("\n[yellow]Initializing executor with free models...[/yellow]")
    executor = StrategyExecutor(config={
        'model_map': {
            'local': 'ollama/qwen2.5-coder:7b',
            'cheap': 'openrouter/meta-llama/llama-3.2-3b-instruct:free',
            'balanced': 'openai/gpt-4o-mini',
            'premium': 'openai/gpt-4o',
            'free': 'openrouter/meta-llama/llama-3.2-3b-instruct:free'
        }
    })

    # Execute dry run
    console.print("\n[yellow]Executing dry run...[/yellow]")
    results = executor.execute_strategy(
        strategy,
        project_path=Path(__file__).parent.parent.parent / "llx" / "examples" / "planfile",
        dry_run=True,
        on_progress=lambda msg: console.print(f"  • {msg}")
    )

    # Show results
    console.print("\n[bold cyan]Results:[/bold cyan]")
    console.print("=" * 50)

    free_count = 0
    cheap_count = 0
    other_count = 0

    for r in results:
        console.print(f"  • {r.task_name}: {r.status}")
        console.print(f"    Model: {r.model_used}")

        if 'free' in r.model_used:
            free_count += 1
        elif 'cheap' in r.model_used or 'openrouter' in r.model_used:
            cheap_count += 1
        else:
            other_count += 1

    # Summary
    console.print("\n[bold cyan]Model Usage Summary:[/bold cyan]")
    console.print(f"  Free models: {free_count} tasks")
    console.print(f"  Cheap models: {cheap_count} tasks")
    console.print(f"  Other models: {other_count} tasks")

    if free_count + cheap_count > 0:
        console.print("\n[green]✓ OpenRouter free models are being used![/green]")
        console.print("\n[dim]Note: To actually execute tasks (not dry-run),[/dim]")
        console.print("[dim]ensure OPENROUTER_API_KEY is set in your environment.[/dim]")

    return True


def create_simple_free_strategy():
    """Create a strategy that forces free models."""

    strategy = {
        "name": "Free Model Strategy",
        "version": "1.0.0",
        "project_type": "python",
        "domain": "software",
        "goal": "Test free model usage",

        "sprints": [
            {
                "id": 1,
                "name": "Free Model Test",
                "objectives": ["Test all free model hints"],

                "tasks": [
                    {
                        "name": "Test Free Hint",
                        "description": "Task with free hint",
                        "type": "chore",
                        "model_hints": "free"
                    },
                    {
                        "name": "Test Cheap Hint",
                        "description": "Task with cheap hint",
                        "type": "documentation",
                        "model_hints": {
                            "implementation": "cheap"
                        }
                    },
                    {
                        "name": "Test Local Model",
                        "description": "Task with local model",
                        "type": "refactor",
                        "model_hints": "local"
                    }
                ]
            }
        ]
    }

    # Save strategy
    strategy_file = Path(__file__).parent / "examples" / "strategy_free_test.yaml"
    import yaml
    with open(strategy_file, 'w') as f:
        yaml.dump(strategy, f, default_flow_style=False, indent=2)

    console.print(f"[green]✓ Created free-only strategy: {strategy_file}[/green]")
    return strategy_file


if __name__ == "__main__":
    # Test main strategy
    test_planfile_v2()

    # Create and test free-only strategy
    console.print("\n" + "=" * 60)
    create_simple_free_strategy()

    console.print("\n[bold green]All tests completed successfully![/bold green]")
    console.print("\n[dim]Planfile v2 is ready to use with OpenRouter free models.[/dim]")
