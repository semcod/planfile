"""Query command handlers for planfile CLI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from planfile.cli.core import console, print_error
from planfile.core.models import Strategy
from planfile.loaders.yaml_loader import load_strategy_yaml, save_strategy_yaml


def calculate_strategy_stats(strategy: Strategy) -> dict[str, Any]:
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


def stats_cmd(
    strategy_file: str = typer.Argument(..., help="Strategy file to analyze"),
) -> None:
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
        print_error(f"Stats calculation failed: {e}")
        raise typer.Exit(1)


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

        if output:
            Path(output).write_text(json.dumps(comparison, indent=2))
            console.print(f"\n[green]✓[/green] Comparison saved to {output}")

    except Exception as e:
        print_error(f"Comparison failed: {e}")
        raise typer.Exit(1)


def export_cmd(
    strategy_file: str = typer.Argument(..., help="Strategy file to export"),
    format: str = typer.Option("json", "--format", "-f", help="Export format (json, csv, html)"),
    output: str = typer.Option(..., "--output", "-o", help="Output file"),
) -> None:
    """Export strategy to various formats."""
    try:
        strategy = load_strategy_yaml(strategy_file)

        if format == "json":
            Path(output).write_text(json.dumps(strategy.model_dump(), indent=2))
        elif format == "csv":
            _export_to_csv(strategy, output)
        elif format == "html":
            _export_to_html(strategy, output)
        else:
            print_error(f"Unknown format: {format}")
            raise typer.Exit(1)

        console.print(f"[green]✓[/green] Exported to {output}")

    except Exception as e:
        print_error(f"Export failed: {e}")
        raise typer.Exit(1)


def _export_to_csv(strategy: Strategy, file_path: str) -> None:
    """Export strategy to CSV format."""
    import csv

    with open(file_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Type', 'ID', 'Name', 'Description', 'Priority', 'Status'])

        for sprint in strategy.sprints:
            writer.writerow(['Sprint', sprint.id, sprint.name,
                           f"Duration: {getattr(sprint, 'duration', 'N/A')}",
                           '', ''])

        if hasattr(strategy, 'tasks') and strategy.tasks:
            for category, tasks in strategy.tasks.items():
                for task in tasks:
                    writer.writerow(['Task', task.get('id', ''), task.get('name', ''),
                                   task.get('description', ''),
                                   task.get('priority', ''), ''])


def _export_to_html(strategy: Strategy, file_path: str) -> None:
    """Export strategy to HTML format."""
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>{strategy.name}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        h1 {{ color: #333; }}
        h2 {{ color: #666; border-bottom: 2px solid #eee; padding-bottom: 10px; }}
        .sprint {{ margin: 20px 0; padding: 20px; border: 1px solid #ddd; border-radius: 5px; }}
    </style>
</head>
<body>
    <h1>{strategy.name}</h1>
    <p><strong>Goal:</strong> {strategy.goal}</p>
    <p><strong>Project Type:</strong> {strategy.project_type}</p>
    <h2>Sprints</h2>
"""
    for sprint in strategy.sprints:
        html += f"""
    <div class="sprint">
        <h3>{sprint.name}</h3>
        <p><strong>Duration:</strong> {getattr(sprint, 'duration', 'N/A')}</p>
    </div>
"""
    html += "</body></html>"

    with open(file_path, 'w') as f:
        f.write(html)


def merge_cmd(
    strategy_files: list[str] = typer.Argument(..., help="Strategy files to merge"),
    output: str = typer.Option(..., "--output", "-o", help="Output file"),
    name: str | None = typer.Option(None, "--name", "-n", help="Name for merged strategy"),
) -> None:
    """Merge multiple strategies into one."""
    try:
        strategies = [load_strategy_yaml(f) for f in strategy_files]

        # Use Strategy's built-in merge method
        merged = strategies[0].merge(strategies[1:], name=name)

        save_strategy_yaml(merged, output)
        console.print(f"[green]✓[/green] Merged {len(strategies)} strategies into {output}")

    except Exception as e:
        print_error(f"Merge failed: {e}")
        raise typer.Exit(1)
