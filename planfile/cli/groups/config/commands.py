"""Safe configuration commands backed by the shared OQL configuration contract."""

from __future__ import annotations

import json

import typer
import yaml

from planfile.cli.core import console


def _manager(project_path: str):
    from planfile import Planfile

    return Planfile.auto_discover(project_path).configuration


def _emit(payload: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    else:
        console.print(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True))


def register_config_commands(app: typer.Typer) -> None:
    config_app = typer.Typer(
        help="Inspect and safely change Planfile configuration",
        context_settings={"help_option_names": ["-h", "--help"]},
    )

    @config_app.command("list")
    def config_list(
        project_path: str = typer.Option(".", "--project", "-p"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        """List effective, redacted values and writable OQL paths."""
        _emit(_manager(project_path).list(), as_json)

    @config_app.command("show")
    def config_show(
        path: str | None = typer.Argument(None, help="Dot-separated configuration path"),
        project_path: str = typer.Option(".", "--project", "-p"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        """Show all configuration or one redacted value."""
        _emit(_manager(project_path).show(path), as_json)

    @config_app.command("set")
    def config_set(
        path: str = typer.Argument(..., help="Writable dot-separated configuration path"),
        value: str = typer.Argument(..., help="YAML/JSON scalar or collection"),
        project_path: str = typer.Option(".", "--project", "-p"),
        dry_run: bool = typer.Option(False, "--dry-run"),
        if_revision: str | None = typer.Option(
            None,
            "--if-revision",
            help="Apply only when the current configuration has this revision",
        ),
        reason: str = typer.Option("", "--reason"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        """Validate and set one value through the OQL configuration contract."""
        try:
            parsed = yaml.safe_load(value)
            result = _manager(project_path).set_many(
                {path: parsed},
                mode="dry-run" if dry_run else "apply",
                actor="cli",
                reason=reason,
                expected_revision=if_revision,
            )
        except (TypeError, ValueError, yaml.YAMLError) as exc:
            console.print(f"[red]Configuration failed:[/red] {exc}")
            raise typer.Exit(1) from exc
        _emit(result, as_json)

    app.add_typer(config_app, name="config", help="Safe project configuration")
