"""Serve command for planfile CLI."""

import typer
from rich.markup import escape

from planfile.cli.core import console


def serve_cli(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host to bind"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload"),
    workers: int = typer.Option(1, "--workers", "-w", help="Number of workers"),
) -> None:
    """Start the planfile REST API server (FastAPI + uvicorn)."""
    try:
        import uvicorn
    except ImportError:
        # Escape the literal install command so Rich does not swallow ``[api]``
        # as console markup and print a wrong (extras-less) install hint.
        console.print(
            "[red]uvicorn is required. Install with:[/red] "
            + escape("pip install 'planfile[api]'")
        )
        raise typer.Exit(1) from None

    console.print(f"[green]Starting planfile server at[/green] http://{host}:{port}")
    uvicorn.run(
        "planfile.api.server:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers if not reload else 1,
    )
