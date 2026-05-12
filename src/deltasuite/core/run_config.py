"""Build a runnable command for a Delft3D project + kernel installation.

This module decides:

* Which ``run_*.bat`` launcher to invoke.
* What arguments to pass.
* In which working directory the process must run (the project root, so
  that relative file references inside ``.mdf`` / ``.mdu`` resolve).

The result is a :class:`RunConfig`, a plain dataclass with no Qt
dependency, that the GUI's :class:`~deltasuite.app.run_controller.RunController`
turns into a live ``QProcess``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from deltasuite.core.kernels import KernelKind, KernelSet
from deltasuite.core.project import ProjectType
from deltasuite.core.project_detector import DetectedProject


class RunConfigError(RuntimeError):
    """Raised when a project cannot be matched to an available kernel."""


@dataclass(frozen=True, slots=True)
class RunConfig:
    """Everything needed to spawn a single simulation process."""

    program: Path
    """Absolute path to the executable or launcher script to invoke."""

    args: list[str] = field(default_factory=list)
    """Arguments passed to ``program``."""

    working_dir: Path = Path()
    """Directory the process must run from (typically the project root)."""

    extra_env: dict[str, str] = field(default_factory=dict)
    """Additional environment variables merged on top of the parent env."""

    kernel_kind: KernelKind | None = None
    """Identifier of the kernel that will be invoked (for logging/UI)."""

    description: str = ""
    """One-liner shown in the UI (e.g. *"Run Delft3D 4 (f34.mdf)"*)."""


_PROJECT_TO_KERNEL: dict[ProjectType, KernelKind] = {
    ProjectType.DELFT3D4: KernelKind.D_HYDRO,
    ProjectType.DFLOWFM: KernelKind.DFLOWFM,
    ProjectType.DIMR: KernelKind.DIMR,
}


def build_run_config(detected: DetectedProject, kernel_sets: list[KernelSet]) -> RunConfig:
    """Match ``detected`` against the available kernels and build a runnable config.

    :raises RunConfigError: when no compatible kernel is available, or
        when the project type is unknown.
    """
    if detected.project_type is ProjectType.UNKNOWN:
        raise RunConfigError(
            f"Could not identify a Delft3D model in {detected.root}. "
            "Expected a .mdf, .mdu or dimr_config.xml file."
        )

    kernel_kind = _PROJECT_TO_KERNEL[detected.project_type]
    kernel = _select_kernel(kernel_sets, kernel_kind)
    if kernel is None:
        raise RunConfigError(
            f"No '{kernel_kind.value}' kernel was detected. "
            "Run 'deltasuite detect' to see available installations."
        )

    program = kernel.best_command()
    args = _build_args(detected, kernel_kind)
    description = f"Run {detected.description} with {kernel.display_name} ({program.name})"

    return RunConfig(
        program=program,
        args=args,
        working_dir=detected.root,
        kernel_kind=kernel_kind,
        description=description,
    )


def _select_kernel(kernel_sets: list[KernelSet], kind: KernelKind):  # type: ignore[no-untyped-def]
    """Return the first :class:`~deltasuite.core.kernels.KernelInfo` of ``kind``."""
    for ks in kernel_sets:
        info = ks.get(kind)
        if info is not None:
            return info
    return None


def _build_args(detected: DetectedProject, kernel_kind: KernelKind) -> list[str]:
    """Compute the arguments to pass to the launcher.

    * Delft3D 4 launcher: defaults to ``config_d_hydro.xml`` in cwd, but we
      always pass it explicitly when a non-standard name was detected.
    * D-Flow FM launcher: requires the ``.mdu`` file.
    * DIMR launcher: requires the ``dimr_config.xml`` file.
    """
    if detected.main_input is None:
        return []
    name = detected.main_input.name

    if kernel_kind is KernelKind.D_HYDRO:
        if name.lower().endswith(".xml"):
            return [name]
        return []
    if kernel_kind is KernelKind.DFLOWFM:
        return [name]
    if kernel_kind is KernelKind.DIMR:
        return [name]
    return [name]
