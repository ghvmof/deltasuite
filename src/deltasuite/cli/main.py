"""Top-level Typer application for DeltaSuite.

Run ``deltasuite --help`` to list available subcommands.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from deltasuite import APP_NAME, __version__
from deltasuite.cli.detect import detect_command

console = Console()
app = typer.Typer(
    name="deltasuite",
    help=f"{APP_NAME} command-line interface.",
    no_args_is_help=False,
    add_completion=True,
    rich_markup_mode="rich",
)
app.command("detect")(detect_command)


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"[bold cyan]{APP_NAME}[/] version [green]{__version__}[/]")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def root(
    ctx: typer.Context,
    version: Annotated[
        bool | None,
        typer.Option("--version", "-V", help="Show version and exit.", callback=_version_callback),
    ] = None,
    log_level: Annotated[
        str,
        typer.Option(
            "--log-level",
            "-l",
            help="Logging verbosity.",
            case_sensitive=False,
            show_default=True,
        ),
    ] = "INFO",
    log_file: Annotated[
        Path | None,
        typer.Option(
            "--log-file",
            help="Override the path of the log file.",
        ),
    ] = None,
) -> None:
    """Root callback: configure logging and dispatch to the GUI when no subcommand is given."""
    from deltasuite.core import configure_logging

    configure_logging(level=log_level.upper(), log_file=log_file)

    if ctx.invoked_subcommand is None:
        from deltasuite.app.entrypoint import run

        raise typer.Exit(code=run())
