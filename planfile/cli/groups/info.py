"""Project information and summary commands for planfile CLI."""

from __future__ import annotations

import typer
from rich.panel import Panel

from planfile.cli.core import console
from planfile.cli.groups.ticket.commands import _display_tickets, format_markdown_tickets


def register_info_commands(app: typer.Typer) -> None:
    """Register top-level info and summary commands."""

    @app.command("info", help="Project and tickets summary with status metrics, sync links and details.")
    @app.command("summary", help="Alias for planfile info.")
    def info_command(
        sprint: str = typer.Option("current", "-s", "--sprint", help="Sprint to display (default: current, or 'all')"),
        status: str | None = typer.Option(None, help="Filter by status: open|in_progress|review|done|blocked|all"),
        details: bool = typer.Option(False, "-d", "--details", help="Include full ticket details (description, files, criteria)"),
        fmt: str = typer.Option("markdown", "-f", "--format", help="markdown | md | table | json | yaml"),
    ) -> None:
        """Display project summary, sprint metrics and synchronized task list."""
        from planfile import Planfile
        from planfile.integrations.config import IntegrationConfig

        pf = Planfile.auto_discover()
        project_dir = str(pf.store.project_dir)

        gh_repo = ""
        integrations_desc = []
        try:
            ic = IntegrationConfig(project_dir)
            ic.load_configs()
            integrations = ic.config.get("integrations", {})
            for name, cfg in integrations.items():
                if name == "github":
                    gh_repo = cfg.get("repo", "")
                    integrations_desc.append(f"GitHub (`{gh_repo}`)")
                else:
                    integrations_desc.append(name)
        except Exception:
            pass

        filters = {}
        if status and status != "all":
            filters["status"] = status

        sprint_target = None if sprint == "all" else sprint
        tickets = pf.list_tickets(sprint=sprint_target, **filters)

        # Count status metrics
        status_counts: dict[str, int] = {}
        for t in tickets:
            s_val = t.status.value if hasattr(t.status, "value") else str(t.status)
            status_counts[s_val] = status_counts.get(s_val, 0) + 1

        metrics_parts = [f"**{k}**: {v}" for k, v in sorted(status_counts.items())]
        metrics_str = ", ".join(metrics_parts)

        if fmt in ("markdown", "md"):
            out = []
            out.append(f"## 📊 Planfile: Podsumowanie projektu\n")
            out.append(f"- **Katalog projektu**: `{project_dir}`")
            out.append(f"- **Sprint**: `{sprint}` (Łącznie ticketów: **{len(tickets)}**)")
            if metrics_str:
                out.append(f"- **Metryki zadań**: {metrics_str}")
            if integrations_desc:
                out.append(f"- **Zintegrowane backendy**: {', '.join(integrations_desc)}")
            out.append("\n" + format_markdown_tickets(tickets, details=details, gh_repo=gh_repo))
            print("\n".join(out))
            return

        if fmt in ("json", "yaml"):
            _display_tickets(tickets, fmt=fmt, details=details, gh_repo=gh_repo)
            return

        # Table format (Rich console)
        console.print(
            Panel(
                f"[bold cyan]Projekt:[/bold cyan] {project_dir}\n"
                f"[bold cyan]Sprint:[/bold cyan] {sprint} (Łącznie: {len(tickets)})\n"
                f"[bold cyan]Integracje:[/bold cyan] {', '.join(integrations_desc) or 'Brak'}\n"
                f"[bold cyan]Statusy:[/bold cyan] {metrics_str or 'Brak'}",
                title="Planfile Project Info",
                expand=False,
            )
        )
        _display_tickets(tickets, fmt="table", details=details, gh_repo=gh_repo)
