"""Examples CLI commands."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.progress import Progress
from rich.table import Table

console = Console()


def create_examples_app() -> typer.Typer:
    """Create and return the examples sub-app."""
    app = typer.Typer(help="Example commands")

    @app.command("list")
    def list_examples() -> None:
        """List available examples."""
        examples_dir = Path(__file__).parent.parent.parent.parent.parent / "examples"
        examples = _discover_examples(examples_dir)

        if not examples:
            console.print("[dim]No examples found.[/dim]")
            return

        table = Table(title="Available Examples")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Title", style="bold")
        table.add_column("Description")
        table.add_column("Path", style="dim")

        for ex in examples:
            table.add_row(
                ex['name'],
                ex['title'],
                ex.get('description', ''),
                str(ex['path'])
            )

        console.print(table)

    @app.command("run")
    def run_example(
        name: str = typer.Argument(None, help="Example ID to run"),
        all: bool = typer.Option(False, "--all", "-a", help="Run all examples"),
    ) -> None:
        """Run an example."""
        examples_dir = Path(__file__).parent.parent.parent.parent.parent / "examples"
        examples = _discover_examples(examples_dir)

        if all:
            console.print("[bold]Running all examples...[/bold]")
            results = []

            with Progress() as progress:
                task = progress.add_task("Running examples...", total=len(examples))
                for ex in examples:
                    progress.update(task, description=f"Running {ex['name']}...")
                    success, output = _execute_example(ex)
                    results.append((ex['name'], success, output))
                    progress.advance(task)

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

    return app


def _discover_examples(examples_dir: Path) -> list[dict[str, Any]]:
    """Discover all examples in the examples directory."""
    examples = []

    for item in examples_dir.iterdir():
        if item.name.startswith('.'):
            continue

        if item.is_dir():
            # Directory example
            readme = item / "README.md"
            title = item.name.replace('-', ' ').title()
            description = ""

            if readme.exists():
                try:
                    with open(readme) as f:
                        lines = f.readlines()
                        for line in lines:
                            if line.startswith('# '):
                                title = line[2:].strip()
                                break
                            elif line.strip() and not line.startswith('#'):
                                description = line.strip()
                                break
                except:
                    pass

            # Find run script
            run_script = None
            for script in ["run.sh", "run.py"]:
                if (item / script).exists():
                    run_script = item / script
                    break

            examples.append({
                'name': item.name,
                'title': title,
                'description': description,
                'path': item,
                'run_script': run_script
            })

        elif item.suffix in ['.py', '.sh']:
            # Single file example
            examples.append({
                'name': item.stem,
                'title': item.stem.replace('-', ' ').title(),
                'description': f"Single file example: {item.name}",
                'path': item.parent,
                'run_script': item
            })

    return examples


def _execute_example(ex: dict[str, Any]) -> tuple[bool, str]:
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

        # Add timeout to prevent hanging
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        try:
            output, _ = process.communicate(timeout=60)  # 60 second timeout
            return process.returncode == 0, output
        except subprocess.TimeoutExpired:
            process.kill()
            output, _ = process.communicate()
            return False, f"Example timed out after 60 seconds.\nOutput:\n{output}"
    except Exception as e:
        return False, str(e)
    finally:
        os.chdir(original_cwd)
