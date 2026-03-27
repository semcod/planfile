"""
Additional CLI commands for planfile — health check and examples.

NOTE: export, compare, merge, template, stats have been extracted to
      cmd/cmd_export.py, cmd/cmd_compare.py, cmd/cmd_template.py, cmd/cmd_stats.py.
      This file now only contains health and examples commands.
"""

import os
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


def add_extra_commands(app):
    """Add health and examples commands to the CLI app."""

    @app.command("health")
    def health_cmd(
        project_path: str = typer.Argument(".", help="Project path to check"),
    ):
        """Check project health and suggest improvements."""
        try:
            from ..analysis.generator import generator
            
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
            
            # Priority breakdown
            priority_breakdown = summary.get('priority_breakdown', {})
            if priority_breakdown.get('critical', 0) > 0:
                console.print(f"  [red]✗ {priority_breakdown['critical']} critical issues[/red]")
            
            # Recommendations
            console.print("\n[bold]Recommendations:[/bold]")
            
            if priority_breakdown.get('critical', 0) > 0:
                console.print("  1. Address critical issues immediately")
            
            if total_issues > 20:
                console.print("  2. Consider breaking into multiple sprints")
            
            console.print("  3. Run: planfile generate-from-files . --focus quality")
            console.print("  4. Set up regular health checks")
            
        except Exception as e:
            console.print(f"[red]✗[/red] Health check failed: {e}")
            raise typer.Exit(1)

    # Examples Command Group
    examples_app = typer.Typer(help="Manage and run examples")

    def _get_examples_dir() -> Path:
        """Get the examples directory relative to the package."""
        # Check current working directory first (for dev mode)
        cwd_examples = Path.cwd() / "examples"
        if cwd_examples.exists() and cwd_examples.is_dir():
            return cwd_examples
            
        # Fallback to package location
        package_root = Path(__file__).parent.parent.parent
        package_examples = package_root / "examples"
        if package_examples.exists() and package_examples.is_dir():
            return package_examples
            
        return None

    def _discover_examples() -> List[Dict[str, Any]]:
        """Discover all examples in the examples directory."""
        examples_dir = _get_examples_dir()
        if not examples_dir:
            return []
            
        examples = []
        for item in examples_dir.iterdir():
            if item.is_dir() and not item.name.startswith(('.', '__')):
                # Check for run.sh or .py files
                run_sh = item / "run.sh"
                py_files = list(item.glob("*.py"))
                
                if run_sh.exists() or py_files:
                    title = item.name.replace("-", " ").title()
                    description = ""
                    readme = item / "README.md"
                    if readme.exists():
                        with open(readme, 'r') as f:
                            first_line = f.readline().strip('#').strip()
                            if first_line:
                                title = first_line
                            description = f.readline().strip()
                            if not description:
                                description = f.readline().strip()

                    examples.append({
                        'name': item.name,
                        'path': item,
                        'title': title,
                        'description': description,
                        'run_script': run_sh if run_sh.exists() else (py_files[0] if py_files else None)
                    })
        
        # Also check ecosystem subfolder
        ecosystem_dir = examples_dir / "ecosystem"
        if ecosystem_dir.exists() and ecosystem_dir.is_dir():
            for item in ecosystem_dir.iterdir():
                if item.is_file() and not item.name.startswith('.'):
                    if item.suffix in ('.sh', '.py'):
                        examples.append({
                            'name': f"ecosystem/{item.name}",
                            'path': item,
                            'title': item.name,
                            'description': "Ecosystem integration example",
                            'run_script': item
                        })

        return sorted(examples, key=lambda x: x['name'])

    @examples_app.command("list")
    def list_examples():
        """List all available examples."""
        examples = _discover_examples()
        if not examples:
            console.print("[yellow]⚠[/yellow] No examples found.")
            return

        table = Table(title="Available Examples")
        table.add_column("ID", style="cyan")
        table.add_column("Title", style="green")
        table.add_column("Description", style="white")

        for ex in examples:
            table.add_row(ex['name'], ex['title'], ex['description'])

        console.print(table)
        console.print("\nRun an example with: [bold]planfile examples run <id>[/bold]")
        console.print("Run all examples with: [bold]planfile examples run --all[/bold]")

    @examples_app.command("run")
    def run_example(
        name: Optional[str] = typer.Argument(None, help="Example ID to run"),
        all: bool = typer.Option(False, "--all", "-a", help="Run all examples"),
    ):
        """Run a specific example or all of them."""
        examples = _discover_examples()
        
        if all:
            if not examples:
                console.print("[red]✗[/red] No examples found to run.")
                raise typer.Exit(1)
                
            console.print(Panel("[bold]Running All Examples[/bold]"))
            results = []
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                for ex in examples:
                    # Skip ecosystem scripts in "all" run if they are too many or too complex
                    if "ecosystem/" in ex['name']:
                         continue
                         
                    task_id = progress.add_task(f"Running {ex['name']}...", total=None)
                    
                    success, output = _execute_example(ex)
                    results.append((ex['name'], success, output))
                    
                    if success:
                        progress.update(task_id, description=f"[green]✓ {ex['name']} passed[/green]")
                    else:
                        progress.update(task_id, description=f"[red]✗ {ex['name']} failed[/red]")
            
            # Summary
            console.print("\n[bold]Execution Summary:[/bold]")
            passed = sum(1 for _, s, _ in results if s)
            failed = len(results) - passed
            
            for name, success, _ in results:
                status = "[green]PASS[/green]" if success else "[red]FAIL[/red]"
                console.print(f"  {status} {name}")
                
            console.print(f"\n[bold]Total: {len(results)} | Passed: {passed} | Failed: {failed}[/bold]")
            
            if failed > 0:
                raise typer.Exit(1)
            return

        if not name:
            console.print("[yellow]⚠[/yellow] Provide an example ID to run or use --all.")
            list_examples()
            return

        # Find specific example
        ex = next((e for e in examples if e['name'] == name), None)
        if not ex:
            console.print(f"[red]✗[/red] Example '{name}' not found.")
            raise typer.Exit(1)

        console.print(f"[bold]Running {ex['title']}...[/bold]")
        success, output = _execute_example(ex)
        
        if success:
            console.print(f"\n[green]✓ Example '{name}' completed successfully.[/green]")
        else:
            console.print(f"\n[red]✗ Example '{name}' failed.[/red]")
            console.print("\n[bold]Output:[/bold]")
            console.print(output)
            raise typer.Exit(1)

    def _execute_example(ex: Dict[str, Any]) -> tuple:
        """Execute a single example and return status and output."""
        script = ex['run_script']
        if not script:
            return False, "No run script found."
            
        original_cwd = os.getcwd()
        try:
            if ex['path'].is_dir():
                os.chdir(ex['path'])
                cmd = ["bash", "run.sh"] if script.name == "run.sh" else ["python3", script.name]
            else:
                # Single file example
                os.chdir(ex['path'].parent)
                cmd = ["bash", script.name] if script.suffix == ".sh" else ["python3", script.name]
                
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )
            output, _ = process.communicate()
            return process.returncode == 0, output
        except Exception as e:
            return False, str(e)
        finally:
            os.chdir(original_cwd)

    app.add_typer(examples_app, name="examples")
