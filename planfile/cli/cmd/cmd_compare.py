"""Compare strategies CLI command — extracted from extra_commands.py."""

import json
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel

from planfile.core.models import Strategy
from planfile.loaders.yaml_loader import load_strategy_yaml

console = Console()


def compare_strategies(s1: Strategy, s2: Strategy) -> dict[str, Any]:
    """Compare two strategies and return differences."""
    comparison = {
        'common_elements': [],
        'differences': [],
        'only_in_s1': [],
        'only_in_s2': [],
        'similarity_score': 0.0
    }

    goals1 = set(getattr(s1, 'goals', []))
    goals2 = set(getattr(s2, 'goals', []))

    comparison['common_elements'].extend(list(goals1 & goals2))
    comparison['differences'].extend([
        {'goal': g, 'in': 's1'} for g in goals1 - goals2
    ])
    comparison['differences'].extend([
        {'goal': g, 'in': 's2'} for g in goals2 - goals1
    ])

    sprints1 = {s.id: s for s in s1.sprints}
    sprints2 = {s.id: s for s in s2.sprints}

    common_sprints = set(sprints1.keys()) & set(sprints2.keys())
    comparison['only_in_s1'].extend([s.id for s in sprints1.values() if s.id not in sprints2])
    comparison['only_in_s2'].extend([s.id for s in sprints2.values() if s.id not in sprints1])

    total_elements = len(goals1) + len(goals2) + len(sprints1) + len(sprints2)
    common_elements = len(goals1 & goals2) + len(common_sprints)
    comparison['similarity_score'] = (2 * common_elements) / total_elements if total_elements > 0 else 0

    return comparison


def register_compare_commands(app: typer.Typer) -> None:
    """Register compare command on the typer app."""

    @app.command("compare")
    def compare_cmd(
        strategy1: str = typer.Argument(..., help="First strategy file"),
        strategy2: str = typer.Argument(..., help="Second strategy file"),
        output: str | None = typer.Option(None, help="Save comparison to file"),
    ) -> None:
        """Compare two strategies."""
        try:
            s1 = load_strategy_yaml(strategy1)
            s2 = load_strategy_yaml(strategy2)

            comparison = compare_strategies(s1, s2)

            console.print(Panel(f"[bold]Strategy Comparison[/bold]\nSimilarity: {comparison['similarity_score']:.2%}"))

            if comparison['common_elements']:
                console.print("\n[green]Common Elements:[/green]")
                for item in comparison['common_elements']:
                    console.print(f"  • {item}")

            if comparison['differences']:
                console.print("\n[yellow]Differences:[/yellow]")
                for diff in comparison['differences']:
                    console.print(f"  • {diff}")

            if comparison['only_in_s1']:
                console.print(f"\n[blue]Only in {strategy1}:[/blue]")
                for item in comparison['only_in_s1']:
                    console.print(f"  • {item}")

            if comparison['only_in_s2']:
                console.print(f"\n[blue]Only in {strategy2}:[/blue]")
                for item in comparison['only_in_s2']:
                    console.print(f"  • {item}")

            if output:
                with open(output, 'w') as f:
                    json.dump(comparison, f, indent=2, default=str)
                console.print(f"\n[green]✓[/green] Comparison saved to {output}")

        except Exception as e:
            console.print(f"[red]✗[/red] Comparison failed: {e}")
            raise typer.Exit(1)
