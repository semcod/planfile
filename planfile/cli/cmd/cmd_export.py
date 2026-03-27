"""Export and merge CLI commands — extracted from extra_commands.py."""

import json

import typer
from rich.console import Console

from planfile.core.models import Strategy
from planfile.loaders.yaml_loader import load_strategy_yaml, save_strategy_yaml

console = Console()


def export_to_csv(strategy: Strategy, file_path: str) -> None:
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


def export_to_html(strategy: Strategy, file_path: str) -> None:
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
        .task {{ margin: 10px 0; padding: 10px; background: #f9f9f9; border-radius: 3px; }}
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
        <p><strong>Objectives:</strong></p>
        <ul>
"""
        for obj in getattr(sprint, 'objectives', []):
            html += f"            <li>{obj}</li>\n"
        html += "        </ul>\n    </div>\n"

    html += """
</body>
</html>
"""

    with open(file_path, 'w') as f:
        f.write(html)


def register_export_commands(app: typer.Typer) -> None:
    """Register export and merge commands on the typer app."""

    @app.command("export")
    def export_cmd(
        strategy_file: str = typer.Argument(..., help="Strategy file to export"),
        output: str = typer.Option(..., help="Output file path"),
        format: str = typer.Option("markdown", help="Export format: yaml, json, csv, html, markdown"),
    ) -> None:
        """Export strategy to various formats."""
        try:
            strategy = load_strategy_yaml(strategy_file)

            if format == "yaml":
                save_strategy_yaml(strategy, output)
            elif format == "json":
                with open(output, 'w') as f:
                    json.dump(strategy.model_dump(), f, indent=2, default=str)
            elif format == "csv":
                export_to_csv(strategy, output)
            elif format == "html":
                export_to_html(strategy, output)
            elif format == "markdown":
                from planfile.loaders.cli_loader import export_results_to_markdown
                results = {'strategy': strategy.model_dump()}
                export_results_to_markdown(results, output)
            else:
                console.print(f"[red]Unsupported format: {format}[/red]")
                raise typer.Exit(1)

            console.print(f"[green]✓[/green] Exported to {output}")

        except Exception as e:
            console.print(f"[red]✗[/red] Export failed: {e}")
            raise typer.Exit(1)

    @app.command("merge")
    def merge_cmd(
        files: list[str] = typer.Argument(..., help="Paths to strategy files to merge"),
        output: str = typer.Option("merged-strategy.yaml", "--output", "-o", help="Output file path"),
        name: str | None = typer.Option(None, "--name", "-n", help="Name for the merged strategy"),
    ) -> None:
        """Merge multiple planfile strategies into one."""
        try:
            if len(files) < 2:
                console.print("[yellow]⚠[/yellow] Provide at least two strategy files to merge.")
                raise typer.Exit(1)

            strategies = []
            for f in files:
                console.print(f"[dim]Loading '{f}'...[/dim]")
                strategies.append(load_strategy_yaml(f))

            base_strategy = strategies[0]
            merged = base_strategy.merge(strategies[1:], name=name)

            save_strategy_yaml(merged, output)

            console.print(f"[green]✓[/green] Successfully merged {len(files)} strategies.")
            console.print(f"  Name: {merged.name}")
            console.print(f"  Total sprints: {len(merged.sprints)}")
            console.print(f"  Output saved to: {output}")
        except Exception as e:
            console.print(f"[red]✗[/red] Merge failed: {e}")
            raise typer.Exit(1)
