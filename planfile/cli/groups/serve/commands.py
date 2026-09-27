"""Serve command for planfile CLI."""

import typer
from rich.markup import escape

from planfile.cli.core import console
from planfile.cli.groups.serve.local import serve_endpoint
from planfile.cli.groups.serve.restart import RestartError


def serve_cli(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host to bind"),
    port: int = typer.Option(
        8000, "--port", "-p", min=0, max=65535, help="Port to bind or restart"
    ),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload"),
    workers: int = typer.Option(1, "--workers", "-w", help="Number of workers"),
) -> None:
    """Start or restart Planfile on the same endpoint; preserve unrelated services.

    A verified local Docker instance is restarted with its existing configuration.
    A local server started by this command is replaced in the foreground.
    """
    try:
        import uvicorn
    except ImportError:
        # Escape the literal install command so Rich does not swallow ``[api]``
        # as console markup and print a wrong (extras-less) install hint.
        console.print(
            "[red]uvicorn is required. Install with:[/red] " + escape("pip install 'planfile[api]'")
        )
        raise typer.Exit(1) from None

    try:
        with serve_endpoint(host, port) as (listener, container_id):
            if container_id is not None:
                console.print(
                    f"[green]Restarted Planfile Docker container {escape(container_id[:12])}[/green] "
                    f"at http://{escape(host)}:{port}; existing container configuration retained."
                )
                return
            console.print(
                f"[green]Starting planfile server at[/green] http://{escape(host)}:{port}"
            )
            uvicorn.run(
                "planfile.api.server:app",
                host=host,
                port=port,
                fd=listener.fileno(),
                reload=reload,
                workers=workers if not reload else 1,
            )
    except (RestartError, OSError) as exc:
        console.print(f"[red]Cannot serve Planfile:[/red] {escape(str(exc))}")
        raise typer.Exit(1) from exc
