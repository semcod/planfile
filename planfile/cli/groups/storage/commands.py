"""Inspect and migrate Planfile ticket storage."""

from __future__ import annotations

import json

import typer

from planfile.cli.core import console


def create_storage_app() -> typer.Typer:
    app = typer.Typer(help="Inspect and migrate ticket storage")

    @app.command("status")
    def storage_status(
        project_path: str = typer.Option(".", "--project", "-p"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        """Show the configured backend, sprint count and physical files."""
        from planfile import Planfile

        pf = Planfile.auto_discover(project_path)
        backend = pf.store.storage_backend()
        sprints = pf.store.list_sprint_summaries()
        payload = {
            "backend": backend,
            "config": pf.store._storage_config(),
            "sprints": sprints,
            "storage_files": sum(
                len(pf.store._sprint_storage_files(item["id"]))
                for item in sprints
            ),
            "tickets": sum(int(item.get("ticket_count", 0)) for item in sprints),
        }
        if as_json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return
        console.print(f"[bold]Backend:[/bold] {backend}")
        console.print(
            f"[bold]Tickets:[/bold] {payload['tickets']} in "
            f"{len(sprints)} sprint(s), {payload['storage_files']} storage file(s)"
        )
        for sprint in sprints:
            console.print(f"  {sprint['id']}: {sprint.get('ticket_count', 0)}")

    @app.command("migrate")
    def storage_migrate(
        backend: str = typer.Option("sharded-yaml", "--backend"),
        shard_size: int = typer.Option(100, "--shard-size", min=1),
        custom_shards: int = typer.Option(16, "--custom-shards", min=1, max=256),
        project_path: str = typer.Option(".", "--project", "-p"),
        yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        """Migrate monolithic sprint YAML to verified, recoverable YAML shards."""
        from planfile import Planfile

        if backend != "sharded-yaml":
            console.print(f"[red]Unsupported migration backend: {backend}[/red]")
            raise typer.Exit(2)
        pf = Planfile.auto_discover(project_path)
        if not yes:
            confirmed = typer.confirm(
                "Create verified shards and move legacy sprint files to a recovery backup?"
            )
            if not confirmed:
                raise typer.Abort()
        try:
            result = pf.configuration.set_many(
                {
                    "store.storage.backend": "sharded-yaml",
                    "store.storage.shard_size": shard_size,
                    "store.storage.custom_shards": custom_shards,
                },
                actor="cli",
                reason="storage migrate",
            )
            report = result.get("operation") or {
                **pf.store._storage_config(),
                "migrated": False,
                "tickets": 0,
                "sprints": 0,
                "backup_dir": "",
            }
        except (ValueError, RuntimeError) as exc:
            console.print(f"[red]Migration failed:[/red] {exc}")
            raise typer.Exit(1) from exc
        if as_json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return
        console.print(
            f"[green]✓ Migrated {report['tickets']} ticket(s) in "
            f"{report['sprints']} sprint(s) to sharded-yaml[/green]"
        )
        console.print(f"Recovery backup: {report['backup_dir']}")

    @app.command("index-status")
    def index_status(
        project_path: str = typer.Option(".", "--project", "-p"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        """Show SQLite materialized-index freshness and size."""
        from planfile import Planfile

        status = Planfile.auto_discover(project_path).store.ticket_index_status()
        if as_json:
            print(json.dumps(status, ensure_ascii=False, indent=2))
            return
        state = "current" if status["current"] else "stale/missing"
        enabled = "enabled" if status["enabled"] else "disabled"
        console.print(f"[bold]SQLite index:[/bold] {enabled}, {state}")
        console.print(
            f"  {status['tickets']} ticket(s), {status['bytes']} bytes, {status['path']}"
        )

    @app.command("index-enable")
    def index_enable(
        project_path: str = typer.Option(".", "--project", "-p"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        """Enable and build the disposable SQLite ticket index."""
        from planfile import Planfile

        pf = Planfile.auto_discover(project_path)
        result = pf.configuration.set_many(
            {"store.storage.index": "sqlite"},
            actor="cli",
            reason="storage index-enable",
        )
        status = result.get("operation") or pf.store.ticket_index_status()
        if as_json:
            print(json.dumps(status, ensure_ascii=False, indent=2))
            return
        console.print(
            f"[green]✓ SQLite index enabled:[/green] {status['tickets']} ticket(s), "
            f"{status['bytes']} bytes"
        )

    @app.command("index-rebuild")
    def index_rebuild(
        project_path: str = typer.Option(".", "--project", "-p"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        """Rebuild SQLite from authoritative YAML and evidence journals."""
        from planfile import Planfile

        status = Planfile.auto_discover(project_path).store.ensure_ticket_index(force=True)
        if as_json:
            print(json.dumps(status, ensure_ascii=False, indent=2))
            return
        console.print(
            f"[green]✓ SQLite index rebuilt:[/green] {status['tickets']} ticket(s), "
            f"{status['bytes']} bytes"
        )

    @app.command("index-disable")
    def index_disable(
        project_path: str = typer.Option(".", "--project", "-p"),
    ) -> None:
        """Disable index reads; keep the disposable DB available for inspection."""
        from planfile import Planfile

        pf = Planfile.auto_discover(project_path)
        result = pf.configuration.set_many(
            {"store.storage.index": "none"},
            actor="cli",
            reason="storage index-disable",
        )
        status = result.get("operation") or pf.store.ticket_index_status()
        console.print(
            f"[green]✓ SQLite index disabled[/green] ({status['tickets']} cached ticket(s) retained)"
        )

    return app
