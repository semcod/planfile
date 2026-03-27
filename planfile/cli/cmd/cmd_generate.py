
import typer
from rich.console import Console

console = Console()

def generate_strategy_cli(
    project_path: str = typer.Argument(".", help="Project path to analyze"),
    output: str = typer.Option("strategy.yaml", help="Output file path"),
    model: str | None = typer.Option(None, help="LiteLLM model ID"),
    sprints: int = typer.Option(3, help="Number of sprints to generate"),
    focus: str | None = typer.Option(None, help="Focus area: complexity, duplication, tests, docs"),
    toon_dir: str | None = typer.Option(None, help="Pre-existing .toon analysis directory"),
    dry_run: bool = typer.Option(False, help="Show prompt but don't call LLM"),
) -> None:
    """Generate strategy.yaml from project analysis + LLM."""
    from planfile.llm.generator import generate_strategy
    from planfile.loaders.yaml_loader import save_strategy_yaml

    try:
        console.print(f"[bold]Analyzing project:[/bold] {project_path}")

        strategy = generate_strategy(
            project_path,
            model=model,
            sprints=sprints,
            focus=focus,
            toon_dir=toon_dir,
            dry_run=dry_run,
        )

        if not dry_run:
            save_strategy_yaml(strategy, output)
            console.print(f"[green]✓[/green] Strategy saved to: {output}")
            console.print(f"  Sprints: {len(strategy.sprints)}")
            total_tasks = sum(len(s.task_patterns) for s in strategy.sprints)
            console.print(f"  Tasks: {total_tasks}")

            if strategy.quality_gates:
                console.print(f"  Quality Gates: {len(strategy.quality_gates)}")

    except Exception as e:
        console.print(f"[red]✗[/red] Generation failed: {e}")
        raise typer.Exit(1)


def generate_from_files_cmd(
    project_path: str = typer.Argument(".", help="Project path to analyze"),
    output: str = typer.Option("planfile-from-files.yaml", help="Output file path"),
    project_name: str | None = typer.Option(None, help="Project name"),
    max_sprints: int = typer.Option(4, help="Maximum number of sprints"),
    focus: str | None = typer.Option(None, help="Focus area: quality, security, performance, testing, documentation"),
    patterns: list[str] | None = typer.Option(None, help="File patterns to analyze"),
    external_tools: bool = typer.Option(False, "--external-tools", help="Use external tools (code2llm, vallm)"),
    compact: bool = typer.Option(False, "--compact", help="Generate compact YAML with minimal data"),
    verbose: bool = typer.Option(False, help="Verbose output"),
) -> None:
    """Generate planfile from file analysis (no LLM required)."""
    from planfile.analysis.generator import generator
    from planfile.loaders.yaml_loader import save_strategy_yaml

    try:
        console.print(f"[bold]Analyzing project files:[/bold] {project_path}")

        if verbose:
            console.print(f"  Project name: {project_name or 'auto-detected'}")
            console.print(f"  Max sprints: {max_sprints}")
            console.print(f"  Focus area: {focus or 'auto-detected'}")
            if patterns:
                console.print(f"  Patterns: {', '.join(patterns)}")

        if external_tools:
            if verbose:
                console.print("  Using external tools (code2llm, vallm, redup)")
            strategy = generator.generate_with_external_tools(
                project_path=project_path,
                project_name=project_name,
                max_sprints=max_sprints,
                focus_area=focus,
                compact=compact
            )
        else:
            strategy = generator.generate_from_current_project(
                project_path=project_path,
                project_name=project_name,
                max_sprints=max_sprints,
                focus_area=focus,
                patterns=patterns,
                compact=compact
            )

        save_strategy_yaml(strategy, output)

        console.print(f"[green]✓[/green] Strategy saved to: {output}")

        if isinstance(strategy, dict):
            console.print(f"  Name: {strategy.get('name', 'N/A')}")
            console.print(f"  Sprints: {len(strategy.get('sprints', []))}")

            total_issues = strategy.get('summary', {}).get('total_issues', 0)
            if total_issues > 0:
                console.print(f"  Issues found: {total_issues}")

            if strategy.get('quality_gates'):
                console.print(f"  Quality gates: {len(strategy['quality_gates'])}")

            priority_breakdown = strategy.get('summary', {}).get('priority_breakdown', {})
            if priority_breakdown:
                console.print("\n[bold]Issue Breakdown:[/bold]")
                for priority, count in priority_breakdown.items():
                    color = {
                        'critical': 'red',
                        'high': 'yellow',
                        'medium': 'blue',
                        'low': 'green'
                    }.get(priority, 'white')
                    console.print(f"  {priority}: [{color}]{count}[/{color}]")

        console.print("\n[dim]Next steps:[/dim]")
        console.print(f"  1. Review: planfile validate {output}")
        console.print(f"  2. Apply: planfile apply {output} . --dry-run")
        console.print(f"  3. Execute: planfile apply {output} . --backend <backend>")

    except Exception as e:
        console.print(f"[red]✗[/red] Generation failed: {e}")
        if verbose:
            import traceback
            console.print(traceback.format_exc())
        raise typer.Exit(1)
