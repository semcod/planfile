"""Strategy statistics CLI command — extracted from extra_commands.py."""

from typing import Dict, Any

import typer
from rich.console import Console
from rich.table import Table

from planfile.core.models import Strategy
from planfile.loaders.yaml_loader import load_strategy_yaml

console = Console()


def calculate_strategy_stats(strategy: Strategy) -> Dict[str, Any]:
    """Calculate statistics for a strategy."""
    stats = {
        'total_sprints': len(strategy.sprints),
        'total_duration': 0,
        'total_objectives': 0,
        'avg_sprint_duration': 0,
        'quality_gates': len(getattr(strategy, 'quality_gates', [])),
        'goals': len(getattr(strategy, 'goals', []))
    }

    durations = []
    for sprint in strategy.sprints:
        duration_str = getattr(sprint, 'duration', None) or '2 weeks'
        if isinstance(duration_str, str) and 'week' in duration_str:
            weeks = int(duration_str.split()[0])
            stats['total_duration'] += weeks
            durations.append(weeks)

        objectives = sprint.objectives if hasattr(sprint, 'objectives') else []
        stats['total_objectives'] += len(objectives)

    if durations:
        stats['avg_sprint_duration'] = sum(durations) / len(durations)

    return stats


def register_stats_commands(app: typer.Typer) -> None:
    """Register stats command on the typer app."""

    @app.command("stats")
    def stats_cmd(
        strategy_file: str = typer.Argument(..., help="Strategy file to analyze"),
    ):
        """Show strategy statistics."""
        try:
            strategy = load_strategy_yaml(strategy_file)
            stats = calculate_strategy_stats(strategy)

            table = Table(title=f"Statistics for {strategy.name}")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")

            table.add_row("Total Sprints", str(stats['total_sprints']))
            table.add_row("Total Duration", f"{stats['total_duration']} weeks")
            table.add_row("Avg Sprint Duration", f"{stats['avg_sprint_duration']:.1f} weeks")
            table.add_row("Total Objectives", str(stats['total_objectives']))
            table.add_row("Quality Gates", str(stats['quality_gates']))
            table.add_row("Goals", str(stats['goals']))

            console.print(table)

            console.print("\n[bold]Sprint Breakdown:[/bold]")
            for sprint in strategy.sprints:
                duration = getattr(sprint, 'duration', None) or 'N/A'
                objectives = sprint.objectives if hasattr(sprint, 'objectives') else []
                console.print(f"  • {sprint.name}: {duration}, {len(objectives)} objectives")

        except Exception as e:
            console.print(f"[red]✗[/red] Stats calculation failed: {e}")
            raise typer.Exit(1)
