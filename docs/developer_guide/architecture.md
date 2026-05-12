# Architecture

DeltaSuite is organized in clear layers to keep business logic independent from the GUI.

```
┌─────────────────────────────────────────────────────────────┐
│  Presentation: deltasuite.app   (Qt 6 / PySide6)            │
│  ─ MainWindow, dialogs, theming, actions                    │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│  Domain: deltasuite.core   (no Qt dependency)               │
│  ─ Project, Settings, AppPaths, KernelInfo, KernelSet       │
│  ─ logging_setup, kernels, paths, project, settings         │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│  Infrastructure                                             │
│  ─ deltasuite.io       file I/O (mdf, mdu, NetCDF, ...)     │
│  ─ deltasuite.mesh     MeshKernel wrappers                  │
│  ─ deltasuite.modules  process orchestration per engine     │
│  ─ deltasuite.views    visualization widgets (VTK)          │
└─────────────────────────────────────────────────────────────┘
```

## Why this split?

* **`deltasuite.core` has no Qt imports.** This means it can be unit-tested without spinning up an event loop, reused from a CLI, or embedded in another framework.
* **`deltasuite.app` only contains presentation.** All side-effects (creating projects, loading files, launching kernels) are delegated to `core` or `infrastructure`.
* **Optional dependencies are gated.** Visualization, GIS and Delft3D-specific Python packages live in extras (`pip install deltasuite[viz,gis,science,delft3d]`) so a minimal install boots fast.

## Threading model

* The Qt main thread owns the UI.
* Long-running tasks (running a simulation, parsing large NetCDF) are dispatched to `QThread` or `concurrent.futures` pools.
* IPC with simulation kernels uses `QProcess` (Phase 1+) so the user can pause / cancel and watch the log stream live.

## Logging

DeltaSuite uses Loguru. The same logger sinks both to the user's log file (`%LOCALAPPDATA%\DeltaSuite\Logs\deltasuite.log`) and to the GUI's *Output* dock.

## Settings persistence

User settings are stored as TOML in `~/.config/DeltaSuite/settings.toml` (Linux), `%APPDATA%\DeltaSuite\settings.toml` (Windows) or `~/Library/Application Support/DeltaSuite/settings.toml` (macOS), via [`platformdirs`](https://pypi.org/project/platformdirs/) and validated by [`pydantic`](https://docs.pydantic.dev/).
