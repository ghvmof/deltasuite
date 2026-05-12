"""``deltasuite detect`` subcommand: list discovered Delft3D kernels."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from deltasuite.core.kernels import detect_kernels

console = Console()


def detect_command(
    extra_path: Annotated[
        list[Path] | None,
        typer.Option(
            "--path",
            "-p",
            help="Additional directory to search (can be passed multiple times).",
        ),
    ] = None,
    no_path: Annotated[
        bool,
        typer.Option("--no-path", help="Do not search the system PATH."),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print results as JSON."),
    ] = False,
) -> None:
    """Detect compiled Delft3D kernels installed on this machine."""
    sets = detect_kernels(extra_paths=extra_path, include_path=not no_path)

    if json_output:
        payload = [
            {
                "bin_dir": str(s.bin_dir),
                "kernels": {
                    k.name: {
                        "executable": str(k.executable),
                        "launcher": str(k.launcher) if k.launcher else None,
                        "version": k.version,
                        "size_mb": k.size_mb,
                    }
                    for k in s
                },
            }
            for s in sets
        ]
        console.print_json(data=payload)
        return

    if not sets:
        console.print("[yellow]No Delft3D kernels detected.[/]")
        console.print(
            "Hint: set [cyan]DELTASUITE_KERNEL_DIR[/] to point at your "
            "[bold]install_*/bin[/] folder, or pass [cyan]--path[/]."
        )
        raise typer.Exit(code=1)

    warnings: list[tuple[str, str, list[str]]] = []
    for ks in sets:
        table = Table(
            title=f"[bold cyan]{ks.bin_dir}[/]",
            show_header=True,
            header_style="bold magenta",
            border_style="dim",
        )
        table.add_column("Kernel", style="cyan")
        table.add_column("Executable")
        table.add_column("Launcher", style="green")
        table.add_column("Size (MB)", justify="right")
        table.add_column("Version", style="dim")
        table.add_column("Runtime", justify="center")

        for kernel in ks:
            missing = kernel.missing_runtime_dlls()
            runtime_status = "[green]ok[/]" if not missing else "[yellow]incomplete[/]"
            if missing:
                warnings.append((kernel.display_name, str(kernel.executable), missing))
            table.add_row(
                kernel.display_name,
                kernel.executable.name,
                kernel.launcher.name if kernel.launcher else "—",
                f"{kernel.size_mb:.2f}",
                kernel.version or "—",
                runtime_status,
            )
        console.print(table)
        console.print()

    total = sum(len(s) for s in sets)
    console.print(f"[bold green]Found {total} kernel(s) in {len(sets)} location(s).[/]")

    if warnings:
        console.print()
        console.print("[bold yellow]Runtime DLL warnings:[/]")
        for name, path, missing in warnings:
            console.print(
                f"  [yellow]•[/] {name}: missing [red]{', '.join(missing)}[/] near [dim]{path}[/]"
            )
        console.print(
            "[dim]Use the run_*.bat launcher (DeltaSuite does this by default) "
            "or copy missing DLLs into the bin directory.[/]"
        )
