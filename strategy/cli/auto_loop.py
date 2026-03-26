"""
Auto-loop CLI command for sprintstrat.
"""
import typer
from pathlib import Path
from typing import Optional, List
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from ..ci_runner import CIRunner
from ..integrations.github import GitHubBackend
from ..integrations.jira import JiraBackend
from ..integrations.gitlab import GitLabBackend
import os

console = Console()


def get_backend(backend_type: str) -> Any:
    """Get backend instance by type."""
    if backend_type == "github":
        return GitHubBackend(
            repo=os.environ.get("GITHUB_REPO"),
            token=os.environ.get("GITHUB_TOKEN")
        )
    elif backend_type == "jira":
        return JiraBackend(
            base_url=os.environ.get("JIRA_URL"),
            email=os.environ.get("JIRA_EMAIL"),
            token=os.environ.get("JIRA_TOKEN"),
            project=os.environ.get("JIRA_PROJECT")
        )
    elif backend_type == "gitlab":
        return GitLabBackend(
            url=os.environ.get("GITLAB_URL", "https://gitlab.com"),
            token=os.environ.get("GITLAB_TOKEN"),
            project_id=os.environ.get("GITLAB_PROJECT_ID")
        )
    else:
        raise ValueError(f"Unknown backend: {backend_type}")


@app.command("auto-loop")
def auto_loop(
    strategy: Path = typer.Argument(..., help="Strategy YAML file"),
    project_path: Path = typer.Argument(".", help="Project directory"),
    backend: List[str] = typer.Option([], "--backend", "-b", 
                                     help="PM backends (github, jira, gitlab)"),
    max_iterations: int = typer.Option(10, "--max-iterations", "-m", 
                                      help="Maximum loop iterations"),
    auto_fix: bool = typer.Option(False, "--auto-fix", "-a", 
                                 help="Enable LLM auto-fix"),
    llx_command: str = typer.Option("llx", "--llx", "-l", 
                                   help="LLX command to use"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", 
                                        help="Save results to file"),
    dry_run: bool = typer.Option(False, "--dry-run", "-d", 
                                help="Simulate without creating tickets")
):
    """
    Run automated CI/CD loop: test → ticket → fix → retest.
    
    This command will:
    1. Run tests and code analysis
    2. If tests fail, generate bug reports with LLM
    3. Create tickets in configured PM systems
    4. Optionally attempt auto-fix with LLM
    5. Repeat until tests pass or max iterations reached
    """
    console.print("[bold blue]🚀 SprintStrat Auto-Loop CI/CD[/bold blue]")
    console.print(f"Strategy: {strategy}")
    console.print(f"Project: {project_path}")
    console.print(f"Backends: {', '.join(backend) or 'None'}")
    console.print(f"Max iterations: {max_iterations}")
    console.print(f"Auto-fix: {'enabled' if auto_fix else 'disabled'}")
    console.print()
    
    # Validate strategy exists
    if not strategy.exists():
        console.print(f"[red]✗ Strategy file not found: {strategy}[/red]")
        raise typer.Exit(1)
    
    # Initialize backends
    backends = {}
    for b in backend:
        try:
            backends[b] = get_backend(b)
            console.print(f"✓ Initialized {b} backend")
        except Exception as e:
            console.print(f"[red]✗ Failed to initialize {b} backend: {e}[/red]")
            raise typer.Exit(1)
    
    if not backends and not dry_run:
        console.print("[yellow]⚠️  No backends configured - will run in dry-run mode[/yellow]")
        dry_run = True
    
    # Create runner
    runner = CIRunner(
        strategy_path=str(strategy),
        project_path=str(project_path),
        backends=backends,
        llx_command=llx_command,
        max_iterations=max_iterations,
        auto_fix=auto_fix
    )
    
    # Run loop with progress
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Running CI/CD loop...", total=None)
        
        if dry_run:
            console.print("\n[yellow]🔶 DRY RUN MODE - No tickets will be created[/yellow]")
        
        results = runner.run_loop()
        progress.update(task, completed=True)
    
    # Display results
    console.print("\n[bold]📊 Results Summary[/bold]")
    console.print("=" * 50)
    
    # Summary table
    table = Table(title="Iteration Summary")
    table.add_column("Iteration", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Tests", style="yellow")
    table.add_column("Coverage", style="blue")
    table.add_column("Tickets", style="magenta")
    
    for iteration in results["iterations"]:
        status = "✅" if iteration["tests_passed"] else "❌"
        tests = "Pass" if iteration["tests_passed"] else f"Fail ({len(iteration.get('failed_tests', []))})"
        coverage = f"{iteration.get('coverage', 0):.1f}%"
        tickets = str(len(iteration.get("tickets_created", [])))
        
        table.add_row(
            str(iteration["iteration"]),
            status,
            tests,
            coverage,
            tickets
        )
    
    console.print(table)
    
    # Final status
    if results["success"]:
        console.print("\n[green]✅ Loop completed successfully![/green]")
        console.print(f"Strategy '{runner.strategy.name}' is complete!")
    else:
        console.print(f"\n[red]❌ Loop failed: {results['final_status']}[/red]")
        console.print(f"Total iterations: {results['total_iterations']}")
    
    # Ticket summary
    if results["tickets_created"]:
        console.print(f"\n📫 Tickets created: {len(results['tickets_created'])}")
        for url in results["tickets_created"][:5]:  # Show first 5
            console.print(f"  • {url}")
        if len(results["tickets_created"]) > 5:
            console.print(f"  ... and {len(results['tickets_created']) - 5} more")
    
    # Save results
    if output or not results["success"]:
        output_path = output or Path("ci-results.json")
        runner.save_results(results, str(output_path))
    
    # Exit with appropriate code
    raise typer.Exit(0 if results["success"] else 1)


@app.command("ci-status")
def ci_status(
    project_path: Path = typer.Argument(".", help="Project directory"),
):
    """Check current CI status without running tests."""
    console.print("[bold blue]🔍 CI Status Check[/bold blue]")
    
    # Check for recent results
    results_file = project_path / "ci-results.json"
    if results_file.exists():
        import json
        results = json.loads(results_file.read_text())
        
        console.print(f"\nLast run: {results.get('timestamp', 'Unknown')}")
        console.print(f"Status: {results.get('final_status', 'Unknown')}")
        console.print(f"Iterations: {results.get('total_iterations', 0)}")
        
        if results.get("success"):
            console.print("[green]✅ Last run successful[/green]")
        else:
            console.print("[red]❌ Last run failed[/red]")
    else:
        console.print("No CI results found")
    
    # Check test coverage
    coverage_file = project_path / "coverage.json"
    if coverage_file.exists():
        import json
        coverage_data = json.loads(coverage_file.read_text())
        coverage = coverage_data.get("totals", {}).get("percent_covered", 0)
        console.print(f"\nCurrent coverage: {coverage:.1f}%")
    
    # Check for strategy
    strategy_files = list(project_path.glob("**/strategy*.yaml"))
    if strategy_files:
        console.print(f"\nFound strategies: {len(strategy_files)}")
        for f in strategy_files[:3]:
            console.print(f"  • {f}")


# Add to main CLI
from .commands import app
app.add_typer(typer.Typer(name="auto", help="Automated CI/CD commands"), name="auto")
