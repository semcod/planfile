"""Health check CLI commands."""

from __future__ import annotations

import json
import signal
import subprocess
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

console = Console()


def create_health_app() -> typer.Typer:
    """Create and return the health sub-app."""
    app = typer.Typer(help="Health check commands")

    @app.command("check")
    def health_cmd(
        project_path: str = typer.Argument(".", help="Project path to check"),
        timeout: float = typer.Option(8.0, "--timeout", min=0.1, help="Maximum analysis time in seconds"),
        max_files: int = typer.Option(5000, "--max-files", min=1, help="Maximum files to read"),
        max_bytes: int = typer.Option(25 * 1024 * 1024, "--max-bytes", min=1, help="Maximum bytes to read"),
        output_format: str = typer.Option("text", "--format", help="Output format: text or json"),
    ) -> None:
        """Check project health with a bounded, read-only analysis."""
        if output_format not in {"text", "json"}:
            raise typer.BadParameter("format must be text or json", param_hint="--format")

        root = _repository_root(Path(project_path))
        payload: dict[str, Any] = {
            "status": "ok",
            "project_path": str(root),
            "limits": {
                "timeout_seconds": timeout,
                "max_files": max_files,
                "max_bytes": max_bytes,
            },
            "analysis": {"files": 0, "bytes": 0, "truncated": False},
            "summary": {},
            "diagnostics": [],
        }
        try:
            from planfile.analysis.file_analyzer import FileAnalyzer

            with _analysis_deadline(timeout):
                result = FileAnalyzer().analyze_directory(
                    root,
                    ["*.yaml", "*.yml", "*.json", "*.toon.yaml", "*.toon.yml", "*.py"],
                    max_files=max_files,
                    max_bytes=max_bytes,
                )

            payload["summary"] = result["summary"]
            payload["analysis"] = result["budget"]
            if result["budget"]["truncated"]:
                payload["status"] = "budget_exceeded"
                payload["diagnostics"].append({
                    "code": "HEALTH_BUDGET_EXCEEDED",
                    "message": "Analysis budget reached before the repository was fully read.",
                })
            issues = result.get("issues", [])

            if output_format == "json":
                typer.echo(json.dumps(payload, ensure_ascii=False, sort_keys=True))
                if payload["status"] != "ok":
                    raise typer.Exit(1)
                return

            console.print("[bold]Analyzing project health...[/bold]")
            summary = payload["summary"]

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
            if issues:
                console.print("\n[bold]Top Issues:[/bold]")
                for issue in issues[:5]:
                    priority = _issue_value(issue, "priority", "normal")
                    title = _issue_value(issue, "name", None) or _issue_value(issue, "title", None) or "Unknown"
                    if priority == 'critical':
                        console.print(f"  [red]✗[/red] {title}")
                    elif priority == 'high':
                        console.print(f"  [yellow]⚠[/yellow] {title}")
                    else:
                        console.print(f"  [blue]•[/blue] {title}")

            if payload["status"] != "ok":
                console.print(f"[yellow]⚠[/yellow] {payload['diagnostics'][0]['message']}")
                raise typer.Exit(1)

        except HealthAnalysisTimeout:
            payload["status"] = "timeout"
            payload["diagnostics"].append({
                "code": "HEALTH_TIMEOUT",
                "message": f"Health analysis exceeded {timeout:.3g}s for {root}.",
            })
            if output_format == "json":
                typer.echo(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            else:
                console.print(f"[red]✗[/red] {payload['diagnostics'][0]['message']}")
            raise typer.Exit(1) from None
        except typer.Exit:
            raise
        except Exception as e:
            payload["status"] = "error"
            payload["diagnostics"].append({"code": "HEALTH_ERROR", "message": str(e)})
            if output_format == "json":
                typer.echo(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            else:
                console.print(f"[red]✗[/red] Error analyzing project {root}: {e}")
            raise typer.Exit(1) from None

    @app.command("cache")
    def cache_cmd(
        project_path: str = typer.Argument(".", help="Project path to check"),
    ) -> None:
        """Audit .fast.json read caches against their source YAML and self-heal drift.

        Catches the class of bug where a concurrent writer races a cache write and a
        later reader trusts a stale (or empty) snapshot forever because it carries a
        matching mtime — see planfile.core.fastio.read_yaml_fast for the mechanism.
        Exits 1 if any drift was found, even when it was healed, so this can be run
        periodically (e.g. by koru) or wired into CI as an early-warning check.
        """
        from pathlib import Path

        from planfile.core.fastio import audit_project_mirrors

        base_dir = Path(project_path).resolve() / ".planfile"
        if not base_dir.exists():
            console.print(f"[yellow]No .planfile/ at {base_dir}[/yellow]")
            raise typer.Exit(0)

        results = audit_project_mirrors(base_dir)
        drift = [r for r in results if not r["ok"]]
        if not drift:
            console.print(f"[green]✓ cache OK[/green] ({len(results)} mirror file(s) checked)")
            raise typer.Exit(0)

        console.print(f"[red]✗ {len(drift)}/{len(results)} cache mirror(s) drifted[/red]")
        for r in drift:
            status = "healed" if r["healed"] else "NOT healed"
            console.print(f"  [yellow]{status}[/yellow] {r['path']}: {r['reason']}")
        raise typer.Exit(1)

    return app


class HealthAnalysisTimeout(TimeoutError):
    """Raised when a health analysis exceeds its wall-clock budget."""


class _analysis_deadline:
    def __init__(self, seconds: float):
        self.seconds = seconds
        self._previous = None

    def __enter__(self):
        if not hasattr(signal, "SIGALRM"):
            return self
        self._previous = signal.getsignal(signal.SIGALRM)

        def _raise_timeout(_signum, _frame):
            raise HealthAnalysisTimeout

        signal.signal(signal.SIGALRM, _raise_timeout)
        signal.setitimer(signal.ITIMER_REAL, self.seconds)
        return self

    def __exit__(self, _exc_type, _exc, _tb):
        if hasattr(signal, "SIGALRM"):
            signal.setitimer(signal.ITIMER_REAL, 0)
            if self._previous is not None:
                signal.signal(signal.SIGALRM, self._previous)
        return False


def _repository_root(project_path: Path) -> Path:
    """Resolve a project to its Git root without walking to a parent store."""
    path = project_path.resolve()
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return path
    return Path(result.stdout.strip()).resolve()


def _issue_value(issue: Any, key: str, default: Any = None) -> Any:
    if isinstance(issue, dict):
        return issue.get(key, default)
    return getattr(issue, key, default)
