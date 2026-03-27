"""Health check CLI command."""

from pathlib import Path
from typing import Dict, Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


def create_health_app():
    """Create and return the health sub-app."""
    app = typer.Typer(help="Health check commands")
    
    @app.command("check")
    def health_cmd(
        project_path: str = typer.Argument(".", help="Project path to check"),
    ):
        """Check project health and suggest improvements."""
        try:
            from planfile.analysis.generator import generator
            
            console.print("[bold]Analyzing project health...[/bold]")
            
            # Quick analysis
            strategy = generator.generate_from_current_project(
                project_path=project_path,
                max_sprints=2
            )
            
            # Show health metrics
            summary = strategy.get('summary', {})
            
            console.print("\n[bold]Health Metrics:[/bold]")
            
            # Issues
            total_issues = summary.get('total_issues', 0)
            if total_issues == 0:
                console.print("  [green]✓ No issues found[/green]")
            else:
                console.print(f"  [yellow]⚠ {total_issues} issues found[/yellow]")
            
            # Complexity
            avg_cc = summary.get('avg_complexity', 0)
            if avg_cc > 10:
                console.print(f"  [red]✓ High complexity: {avg_cc:.1f}[/red]")
            else:
                console.print(f"  [green]✓ Acceptable complexity: {avg_cc:.1f}[/green]")
            
            # Duplication
            duplication = summary.get('duplication', 0)
            if duplication > 5:
                console.print(f"  [red]✓ High duplication: {duplication}%[/red]")
            else:
                console.print(f"  [green]✓ Low duplication: {duplication}%[/green]")
            
            # Recommendations
            console.print("\n[bold]Recommendations:[/bold]")
            for rec in summary.get('recommendations', []):
                console.print(f"  • {rec}")
            
            # Show top issues
            issues = strategy.get('tickets', [])
            if issues:
                console.print("\n[bold]Top Issues:[/bold]")
                for issue in issues[:5]:
                    priority = issue.get('priority', 'normal')
                    title = issue.get('title', 'Unknown')
                    if priority == 'critical':
                        console.print(f"  [red]✗[/red] {title}")
                    elif priority == 'high':
                        console.print(f"  [yellow]⚠[/yellow] {title}")
                    else:
                        console.print(f"  [blue]•[/blue] {title}")
        
        except Exception as e:
            console.print(f"[red]✗[/red] Error analyzing project: {e}")
            raise typer.Exit(1)
    
    return app
