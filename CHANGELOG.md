# Changelog

All notable changes to DeltaSuite will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0a1] - 2026-05-11

First public alpha release. Ships everything needed to open, edit, run
and visualise a Delft3D model end-to-end without leaving the GUI.

### Packaging notes

The Windows installer ships as a one-folder PyInstaller bundle (385 MB
uncompressed, ~150 MB zipped) plus an Inno Setup wrapper that
registers the `.deltasuite` file association. Several non-obvious
quirks were fixed during packaging and are worth documenting because
they affect anyone reusing this build pipeline:

- **ICU symbol mismatch**. PyInstaller eagerly bundles the
  `icuuc.dll` shipped by Anaconda's `netCDF4` package. That copy
  re-exports every ICU symbol with a version suffix
  (`ucnv_open_73`) so multiple ICU runtimes can coexist. PySide6's
  `Qt6Core.dll`, in contrast, links against the canonical names
  (`ucnv_open`) supplied by `C:\Windows\System32\icuuc.dll` on
  Windows 10/11. Without intervention the loader picks the Anaconda
  copy first and Qt6Core fails to load with `WinError 127`.
  `installer/build.py` now scans the bundle after PyInstaller
  finishes and renames any `icuuc.dll`/`icuin.dll` whose exports
  contain `ucnv_open_` to `*.dll.disabled`, transparently letting the
  loader fall back to System32 (which is exactly how PySide6 resolves
  it in development).
- **DLL search override**. `installer/runtime_hook.py` runs before
  any application code and calls `SetDllDirectoryW` to make the
  bundled `PySide6/` win the DLL search over System32 for everything
  *except* ICU, then pre-loads VC++/Qt/shiboken DLLs by bare name.
  The hook also installs a `sys.excepthook` that surfaces every
  bootstrap failure as a Windows MessageBox with the runtime
  diagnostic, instead of a silent black-box crash.
- **Loguru / windowed bootloader**. PyInstaller's `console=False`
  build replaces `sys.stderr` with `None`. `configure_logging` now
  guards against that instead of crashing with
  `TypeError: Cannot log to objects of type 'NoneType'`.

- Welcome screen with action tiles and Recent projects.
- Built-in F34 sample to try the app in one click.
- Project explorer with recursive auto-discovery.
- Setup tab with a generic editor for `.mdf` and `.mdu`
  (lossless round-trip).
- Map tab with curvilinear and UGRID NetCDF support, time slider,
  Play / Pause / Speed playback and CSV export of cross-sections.
- Series tab with multi-station time-series viewer and CSV export.
- Run controller streaming live `stdout`/`stderr` from `d_hydro`,
  `dflowfm-cli`, `dimr` and friends.
- Passive kernel detection that does not load DLLs of `d_hydro.exe`.
- Preferences dialog persisted to TOML; light / dark / auto theming
  applied without restart.
- PyInstaller spec, Inno Setup script and helper `installer/build.py`
  for one-shot Windows installer builds.
- 95 automated tests across `pytest` and `pytest-qt`, full mypy strict
  + ruff lint/format gates green on Python 3.11/3.12/3.13 and on
  Linux/macOS/Windows.

### Added

- **Phase 4 — UX polish & first-impressions**
  - **Interactive welcome screen** with action tiles (New, Open, Open
    folder, Browse examples, Open sample, Detect kernels) and a Recent
    projects panel rendered live.
  - `core/recent.py`: persistent recent-projects list (TOML, 12 by
    default, configurable). Auto-bumped every time a project is opened
    from the menu, the welcome tile or the file dialog. Stale entries
    are pruned automatically.
  - **Open Recent submenu** in the *File* menu, populated from disk and
    keeping the welcome screen in sync.
  - `core/samples.py`: bundled F34 tutorial sample materialised on
    first use under the user data directory; *Open sample* tile launches
    it in one click.
  - **Preferences dialog** with four tabs (General, Kernels, Runner,
    Recent). Theme changes (`auto` / `light` / `dark`) apply immediately
    without restart.
  - **Map tab playback**: Play / Pause button, 5 playback speeds (0.5x
    to 8x) and a Loop toggle that drive the time slider with a `QTimer`.
  - `scripts/capture_screenshots.py`: helper that automates capturing
    PNG screenshots of every workspace tab using synthetic data. Output
    lands under `docs/_static/screenshots/` and is referenced from the
    README.
  - **16 new tests** (`test_recent.py`, `test_samples.py`,
    `test_welcome.py`, `test_result_controls_play.py`) covering recent
    persistence, the bundled sample lifecycle, the welcome widget signal
    flow, and the playback loop / loop-disabled / speed handling.
  - Total: **95 tests** passing.

- **Phase 3 — Time-series viewer & configuration editor**
  - `core/timeseries.py`: `TimeSeriesDataset` reads both D-Flow FM
    `*_his.nc` and Delft3D 4 `trih-*.nc`. It auto-detects the time and
    station dimensions, decodes UGRID `station_name` strings as well as
    Delft3D 4 `NAMST` char arrays, and exposes plottable variables with
    units and long names.
  - `find_history_files()`: scans a project root and tags each NetCDF as
    `his` (FM) or `trih` (D3D4).
  - `views/timeseries_viewer.py`: Matplotlib widget that overlays one
    line per station with auto date-axis formatting and the standard
    navigation toolbar; `to_csv()` exports the visible series.
  - `widgets/timeseries_controls.py`: side panel with file selector,
    variable combo, multi-select station list (`All` / `None` shortcuts)
    and an *Export CSV…* button.
  - `views/timeseries_panel.py`: glue widget embedded as the new
    **Series** tab. Files are auto-discovered when a project is opened or
    after a successful simulation; on success the *Series* tab is
    surfaced when no map output exists.
  - `File → Open Time-series File… (Ctrl+T)`: open any NetCDF history
    file (no project required).
  - `core/config_files.py`: lossless parser / serialiser pair for
    `.mdu` (D-Flow FM, INI-style with sections) and `.mdf` (Delft3D 4,
    flat key/value with `#…#` strings and continuation lines). Order,
    inline comments and unrecognised lines are preserved on round-trip.
  - `editors/keyvalue_editor.py`: generic, format-agnostic
    `KeyValueEditor` that builds a per-section form from a
    `ConfigDocument`. Tracks dirty state, has *Save* / *Reload* actions
    and surfaces inline comments as field hints.
  - **MainWindow** gains a fourth tab — **Setup** — that auto-loads the
    project's `main_input_file` (`.mdf` or `.mdu`) into the editor.
  - **18 new tests** (`test_timeseries.py`, `test_timeseries_viewer.py`,
    `test_config_files.py`, `test_keyvalue_editor.py`) covering the
    NetCDF reader, both file formats with round-trip, the viewer's CSV
    export and editor dirty-state behaviour. Total: **79 tests** passing.
  - `scripts/demo_view_timeseries.py`: synthetic FM history file (6
    stations × 120 hourly steps × 2 variables) opened directly in the
    viewer for visual validation.

- **Phase 2 — Result visualisation**
  - `core/results.py`: `ResultDataset` reads NetCDF outputs from both
    Delft3D 4 (curvilinear `trim-*.nc`, `XCOR/YCOR`) and D-Flow FM (UGRID
    `*_map.nc`, `mesh2d_*`). Lazy `xarray`-backed, context-manager friendly,
    auto-detects the time dimension and lists every plottable 2-D variable
    with units and long names.
  - `find_result_files()`: scans a project directory and classifies each
    NetCDF output as `trim`, `trih`, `map`, `his`, `com` or `unknown`.
  - `views/map_viewer.py`: Matplotlib viewer embedded in Qt with a full
    navigation toolbar (pan, zoom, save). Supports curvilinear
    `pcolormesh` and unstructured `tripcolor` (fan-triangulated faces),
    automatic / fixed colour ranges and on-the-fly colormap changes.
  - `widgets/result_controls.py`: side panel with file selector, variable
    chooser, time slider, colormap selector and manual colour-range
    controls.
  - `views/result_panel.py`: glue widget combining viewer + controls,
    embedded as the new **Map** tab in the workspace.
  - **Main window** now wraps the workspace in a `QTabWidget`
    (Overview / Map). Result files are auto-discovered when a project is
    opened and after each successful simulation; on success the *Map* tab
    is brought to front automatically.
  - `File → Open Result File… (Ctrl+R)`: load any NetCDF file (no project
    required).
  - **9 new tests** (`test_results.py`, `test_map_viewer.py`) covering the
    reader against synthetic curvilinear and UGRID datasets, plus a
    `qtbot` smoke test of the viewer/panel.
  - `scripts/demo_view_results.py`: generate a synthetic Delft3D-style
    NetCDF and open it in the GUI for visual validation.

- **UX — Recursive project discovery**
  - `core.discover_projects()` walks any folder up to a configurable depth,
    pruning noisy directories (`.git`, `.venv`, `__pycache__`, build /
    output folders…) and stopping at the first recognised project per
    branch (so nested `output/` does not generate spurious hits).
  - `File → Open Folder as Project…` now falls back to a recursive scan
    when the chosen folder is not directly a project; with multiple
    candidates it shows a chooser dialog.
  - **New `File → Browse Models in Folder…` (Ctrl+B)** — pick any folder,
    DeltaSuite lists every Delft3D model found inside (e.g. on the official
    Delft3D `examples/` directory it lists 21 models in one click).
  - **Project Explorer is now recursive** — shows the full directory tree
    of the project with file-type colour coding (`.mdf`, `.mdu`, `.grd`,
    `.dep`, `.bnd`, `.nc`, …) and human-readable file sizes.
  - 6 new tests covering recursive discovery, depth limiting and noise
    pruning.

- **Phase 1 — First end-to-end simulation**
  - `core/project_detector.py`: heuristic identification of Delft3D 4 (`.mdf`),
    D-Flow FM (`.mdu`) and DIMR (`dimr_config.xml`) projects from a directory.
  - `core/run_config.py`: matches a detected project against discovered kernels
    and produces a `RunConfig` (program, args, working directory, environment).
  - `app/run_controller.py`: Qt-aware `QProcess` wrapper with a small state
    machine (IDLE → STARTING → RUNNING → FINISHED_OK / FINISHED_ERROR /
    CANCELLED), line-buffered stdout/stderr, graceful stop with kill fallback.
  - **File → Open Folder as Project…** auto-detects the model in any directory
    and creates an in-memory project on the fly (no `deltasuite.toml` required).
  - **Run / Stop** menu and toolbar actions now actually launch the matching
    `run_*.bat` Delft3D launcher with the correct working directory.
  - **Output** dock streams the kernel log live with channel-based colouring
    (system messages in blue, stderr in red, stdout in light grey) and
    auto-scroll.
  - **Status bar** gains an elapsed-time chronometer and a colour-coded run
    state indicator (Idle / Starting… / Running / Finished OK / Finished with
    errors / Cancelled).
  - Tests:
    - `test_project_detector.py` (7 tests, including a real-world check
      against `examples/delft3d4/01_standard/f34/`)
    - `test_run_config.py` (7 tests covering all project types and error
      paths)
    - `test_run_controller.py` (4 integration tests using a fake Python
      kernel script — exercise stdout/stderr capture, exit codes, concurrent
      starts and graceful cancellation)

### Changed

- Detector is now **fully passive**: version metadata is read directly from
  the PE file headers via `version.dll`, so binaries are never spawned during
  scanning. This eliminates the modal Windows dialog that appeared when
  `d_hydro.exe` was probed without its DLL search path configured.
- `KernelInfo.missing_runtime_dlls()` reports missing runtime DLLs (looking
  in `bin/`, `lib/`, `share/` mirroring the launcher behaviour); shown as a
  *Runtime* column in `deltasuite detect`.

## [0.1.0.dev0] — Phase 0 — Foundation

### Added

- **Phase 0 — Foundation**
  - Initial project scaffolding with modern Python tooling (Hatchling, Ruff, Mypy, Pytest)
  - Main Qt window with menus, toolbar and status bar
  - Auto-detection of compiled Delft3D kernels (`d_hydro`, `dflowfm-cli`, `wave`, `delwaq`, `delpar`, `dimr`)
  - Persistent application settings via `platformdirs`
  - Project model with serialization to TOML
  - Logging infrastructure based on `loguru`
  - Command-line entry points: `deltasuite`, `deltasuite-detect`
  - GitHub Actions CI: lint (Ruff), type-check (Mypy), test (Pytest) on Windows / Linux / macOS
  - Sphinx documentation skeleton with auto-generated API reference
  - GPL-3.0 license, CONTRIBUTING and CODE_OF_CONDUCT

[Unreleased]: https://github.com/ghvmof/deltasuite/compare/v0.1.0a1...HEAD
[0.1.0a1]: https://github.com/ghvmof/deltasuite/releases/tag/v0.1.0a1
