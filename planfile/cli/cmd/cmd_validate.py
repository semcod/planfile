import typer
from pathlib import Path
from rich.console import Console

from planfile.loaders.yaml_loader import load_strategy_yaml

console = Console()

def validate_strategy_cli(
    strategy_path: Path = typer.Argument(..., help="Path to strategy YAML file"),
    verbose: bool = typer.Option(False, help="Verbose output"),
):
    """Validate a strategy YAML file."""
    
    try:
        strategy = load_strategy_yaml(strategy_path)
        console.print(f"[green]✓[/green] Strategy is valid!")
        console.print(f"Name: {strategy.name}")
        console.print(f"Project Type: {strategy.project_type}")
        console.print(f"Domain: {strategy.domain}")
        console.print(f"Sprints: {len(strategy.sprints)}")
        console.print(f"Task Patterns: {sum(len(patterns) for patterns in strategy.tasks.values())}")
        
        if verbose:
            console.print("\n[bold]Sprints:[/bold]")
            for sprint in strategy.sprints:
                console.print(f"  - Sprint {sprint.id}: {sprint.name} ({sprint.length_days} days)")
            
            console.print("\n[bold]Task Patterns:[/bold]")
            for category, patterns in strategy.tasks.items():
                console.print(f"  {category}:")
                for pattern in patterns:
                    console.print(f"    - {pattern.id}: {pattern.title}")
    
    except Exception as e:
        console.print(f"[red]✗[/red] Validation failed: {e}")
        raise typer.Exit(1)
