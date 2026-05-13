# Changelog

All notable changes to DeltaSuite will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0a3] - 2026-05-13

### Added

- **Delft3D `.dep` bathymetry reader / writer (`mesh/io_dep.py`)**
  - `DepthField` dataclass: per-node `node_values` array (length
    `mesh.n_nodes`, NaN for missing samples) plus the original
    `missing_value` and the auto-detected `layout` tag for diagnostics.
  - `load_dep_samples(path, mesh)` parses the legacy ASCII format used
    by every Delft3D 4 / SWAN project. Auto-detects the layout from
    the file size and the mesh's `structured_shape`:
    - `corners_extra` (DPV, `(N+1) x (M+1)` values, the most common)
      -- the trailing sentinel row / column is dropped on load;
    - `nodes` (`M x N`, aligned one-to-one with the grid nodes);
    - `centers` (`(M-1) x (N-1)`) is detected and rejected with a
      clear error -- there is no lossless mapping to per-node
      values without interpolation.
  - Recognises both the decimal (`-999.000`) and the scientific
    (`-9.99E+02`) missing-value flavours used in the wild, with a
    configurable tolerance.
  - `save_dep_samples(field, path, mesh)` always writes the canonical
    `corners_extra` layout (twelve scientific-notation values per line),
    serialising NaN samples back to `missing_value` and appending the
    sentinel row / column automatically. Round-trips bit-for-bit
    through `load_dep_samples`.
- **Bathymetry in the *Mesh* tab**
  - New "Bathymetry (.dep)" group in `MeshControls` with an
    *Open depth (.dep)…* button and a *Clear depth* button, plus a
    status label that shows the source file, the `valid / total`
    sample count and the value range once a field is loaded.
  - `MeshViewerWidget` learnt `set_depth(field)`: when a depth field
    is attached, faces are coloured by mean nodal depth via a
    `PolyCollection` and a colourbar is overlaid; the wireframe is
    still drawn on top so the topology stays legible.
  - Loading or clearing a mesh automatically drops the depth field
    (it is keyed by node count, so it cannot survive topology changes).
- **Bathymetry in the *3D* tab**
  - `Mesh3DPanel` now accepts an optional `depth_provider` callable;
    on every `refresh_from_provider()` it pulls the active depth from
    the *Mesh* tab and feeds the values into the existing
    `Mesh3DViewerWidget.set_node_values()` slot. The demo radial
    extrusion is replaced by the real bathymetry as soon as a `.dep`
    is loaded; clearing the depth or the mesh restores it.
  - `MainWindow` wires `MeshPanel.current_depth` as the
    `depth_provider`, so the user only has to load the file once and
    the *3D* tab picks it up automatically when it becomes visible.
- **19 new tests** covering the reader, the writer, NaN round-trips,
  the layout auto-detector (and centres rejection), error paths, plus
  three real-file smoke tests against `f34.dep`, `weir.dep` and
  `coastw20.dep` shipped with the workspace examples (skipped when
  the workspace is not present). Total: **208 tests** passing.

### Changed

- `tests/conftest.py`, `tests/test_hydrolib_adapter.py`,
  `tests/test_recent.py`: ruff `PT001` auto-fix changed
  `@pytest.fixture()` to `@pytest.fixture` -- pure stylistic, no
  behavioural change.

- **Delft3D RGFGRID `.grd` reader / writer (`mesh/io_grd.py`)**
  - `load_grd_mesh()` parses the legacy ASCII format used by every
    `examples/delft3d4/*` project (and by the SWAN sub-models of
    every `examples/dflowfm/*_dwaves` project): comment block,
    `Coordinate System`, optional `Missing Value`, `M N`
    dimensions, `0 0 0` triplet and `2*N` `ETA= i` blocks
    (X-coordinates first, then Y). Tolerant to any number of values
    per line and to UTF-8 / Latin-1 encodings.
  - `save_grd_mesh()` writes a Deltares-style `.grd` from a
    `MeshGeometry` whose `structured_shape` is known (i.e. produced
    by `make_rectangular_mesh` or read from `.grd`); returns a
    structured error for triangulated / locally-refined meshes
    instead of guessing.
  - Vectorised `_build_structured_edges` / `_build_structured_faces`
    using NumPy broadcasting -- a 66×75 `coastw.grd` (~5 k nodes,
    ~10 k edges) loads in under 5 ms.
- **Delft3D `.enc` enclosure reader / writer (`mesh/io_enc.py`)**
  - `Enclosure` dataclass that carries the polygon as `(m, n)`
    integer indices and, when paired with a structured mesh, also
    the corresponding real-world `(x, y)` coordinates.
  - `load_enc()` auto-closes open polygons, ignores comments
    (`*** begin/end external enclosure`), validates index bounds
    when a parent mesh is supplied.
  - `save_enc()` writes the canonical right-aligned 8-column format.
- **Structured-grid bookkeeping in `MeshGeometry`**
  - New optional `structured_shape: tuple[int, int]` field plus
    `is_structured` property; `make_rectangular_mesh` populates it
    automatically with `(n_rows + 1, n_columns + 1)` so the result
    can be round-tripped to `.grd`.
- **Mesh tab dispatches by extension**
  - The *Open mesh…* file dialog now accepts `*.nc *.grd` (with
    a combined "All supported meshes" filter).
  - The *Save mesh as…* dialog defaults to `mesh.grd` for
    structured meshes and `mesh.nc` otherwise; the extension
    chosen by the user picks the writer (`save_grd_mesh` vs
    `save_mesh_to_ugrid_netcdf`).
- **23 new tests** covering both writers, both readers, the
  round-trip path, the GUI dispatcher and a smoke-load of every
  `.grd` / `.enc` shipped with the workspace examples (skipped
  when the workspace is not present). Total: **189 tests** passing.

### Fixed

- **`refine_mesh_inside_polygon` failed on freshly-generated meshes**
  with `ConstraintError: Mesh::FindEdge: Invalid node index: first
  X, second 4294967295`. The `MeshGeometry → meshkernel.Mesh2d`
  converter was passing our padded `face_nodes` matrix straight
  into `meshkernel.Mesh2d`, whose `mesh2d_set` is sensitive to
  the face winding. The fix is to pass *only* `node_x`, `node_y`
  and `edge_nodes` and let MeshKernel rebuild the face topology
  internally. A new regression test
  (`test_refine_inside_polygon_full_extent_regression`) reproduces
  the original GUI scenario.

- **3-D mesh viewer (`views/mesh3d_viewer.py`)**
  - `Mesh3DViewerWidget` -- matplotlib `Axes3D` canvas with the
    standard navigation toolbar; renders the active mesh as a
    `Poly3DCollection` (faces, colour-mapped by mean Z) plus a
    `Line3DCollection` (edges). Two display modes: *flat* (z=0,
    handy as a sanity preview) and *demo extruded* (smooth radial
    sinusoid scaled to ~10 % of the mesh extent).
  - Per-node Z values can be supplied via `set_node_values()` so
    bathymetry / water-level fields can drive the extrusion later
    without changing the API.
- **3-D side controls (`widgets/mesh3d_controls.py`)**
  - `Mesh3DControls` -- mode selector, Z-scale spin box, faces /
    edges toggles, colormap picker (viridis / plasma / magma /
    cividis / turbo / terrain / RdBu_r) and elevation / azimuth
    sliders. Emits one typed Qt signal per control.
- **3-D coordinator (`views/mesh3d_panel.py`)**
  - `Mesh3DPanel` -- splitter that pairs the viewer with its
    controls and pulls the geometry from the *Mesh* tab via a
    `mesh_provider` callable, so the source of truth stays in the
    editor.
- **New 3D tab in `MainWindow`**
  - Wired as the sixth workspace tab (after *Mesh*) and auto-syncs
    with the *Mesh* tab whenever the user switches to it.
  - Graceful `shutdown()` hook.
- **6 new GUI smoke tests** (`tests/test_mesh3d_panel.py`) covering
  the viewer (flat + extruded modes, all setters), the controls
  (default colormaps, mode selection) and the panel (provider sync,
  direct `set_mesh`, signal-driven viewer updates).
  Total: **165 tests** passing.

- **Mesh editing back end (`deltasuite.mesh`)**
  - `mesh/generate.py`: `make_rectangular_mesh()` (uniform M×N grid
    with optional rotation) and `make_triangular_mesh_from_polygon()`
    (Delaunay) wrapping `meshkernel`; both return a structured
    `MeshOpResult` so failures (including missing `meshkernel`) flow
    as data, not exceptions.
  - `mesh/refine.py`: `refine_mesh_inside_polygon()` (Casulli) and
    `refine_mesh_based_on_samples()` (adaptive, sample-driven).
  - `mesh/edit.py`: `orthogonalize_mesh()`, `move_node()`,
    `delete_node()`, `merge_nearby_nodes()` and a pure-Python
    `hanging_edges()` linter.
  - `mesh/io.py`: `save_mesh_to_ugrid_netcdf()` and `round_trip_mesh()`
    -- writes CF-1.8 / UGRID-1.0 NetCDF using D-Flow FM's canonical
    variable names (`mesh2d`, `mesh2d_node_x/y`, `mesh2d_edge_nodes`,
    `mesh2d_face_nodes`) without depending on `meshkernel`.
- **New *Mesh* tab in the main window**
  - `views/mesh_viewer.py`: standalone matplotlib canvas
    (`MeshViewerWidget`) that renders any `MeshGeometry` as a
    `LineCollection` with the navigation toolbar, an aspect-correct
    axis and a one-line summary (`N nodes / N edges / N faces`).
  - `widgets/mesh_controls.py`: side panel with one button per
    high-level operation (Open, Save, Generate rectangular, Refine,
    Orthogonalise, Clear) and the relevant spin boxes; emits one
    typed Qt signal per action so the surrounding panel sequences
    the work.
  - `views/mesh_panel.py`: `MeshPanel` glue widget that owns the
    current `MeshGeometry`, dispatches every `MeshControls` signal to
    the matching `deltasuite.mesh` operation and surfaces errors via
    `QMessageBox` + a status line.
  - Integrated as the fifth workspace tab (after *Series*) in
    `MainWindow`, with a graceful `shutdown()` hook.
- **30 new tests** covering the four back-end modules, the viewer,
  the controls and the panel (signals, button enabling, generate /
  save / open round-trip). Total: **159 tests** passing.

## [0.1.0a2] - 2026-05-13

Second alpha. Adds the official **Deltares Python stack** integration
(`hydrolib-core`, `dfm-tools`, `meshkernel` / `xugrid`) and three new
visible features in the Map tab built on top of those libraries.

### Added

- **hydrolib-core integration (`core/hydrolib_adapter.py`)**
  - `safe_load_fmmodel()` returns a `HydrolibLoadResult` that exposes
    either a typed `FMModel` (when hydrolib-core is installed) or a
    structured error, never raises through the GUI.
  - `fmmodel_section_summary()` / `fmmodel_set_values()` so the Setup
    tab can use the canonical schema without depending on the import
    happening at GUI startup.
  - Cached availability and version probes
    (`is_hydrolib_available`, `hydrolib_version`).
- **dfm-tools integration (`core/dfm_tools_adapter.py`) + U/V vector
  overlay**
  - `open_partitioned_smart()` / `open_curvilinear_smart()` wrap
    `dfmt.open_partitioned_dataset` / `dfmt.open_dataset_curvilinear`
    with graceful fallbacks to plain xarray when dfm-tools is not
    installed.
  - `find_uv_variables()` and `extract_uv_field()` produce a
    library-agnostic `UVField` (x, y, u, v, magnitude, optional time).
  - `MapViewerWidget.set_vector_overlay()` draws the `quiver` on top
    of the colour mesh with configurable colour, scale and stride.
  - `ResultControls` exposes a *Show U/V vectors* row with a stride
    spin box that auto-disables when the dataset has no recognised
    velocity pair.
- **MeshKernel / xugrid integration (`core/mesh_adapter.py`)**
  - Library-agnostic `MeshGeometry` dataclass (nodes, edges, optional
    face-node connectivity) and `MeshLoadResult` wrapper.
  - `load_mesh_from_dataset()` and `load_mesh_from_path()` with two
    backends: `xugrid` when installed (canonical UGRID parser), and a
    pure-numpy heuristic fallback that recognises the standard
    `mesh2d_*` variable names (with automatic 1-based → 0-based
    normalisation for both edge and face connectivity, preserving the
    `-1` sentinel for ragged faces).
  - Cached availability and version probes
    (`is_xugrid_available`, `xugrid_version`,
    `is_meshkernel_available`, `meshkernel_version`) so the GUI can
    enable / disable the wireframe row without paying the cost of
    importing the C++ extension.
  - All eight new symbols re-exported from `deltasuite.core`.
- **Mesh wireframe overlay in the Map tab**
  - `MapViewerWidget.set_mesh_overlay()` adds a thin grey
    `LineCollection` of mesh edges below the U/V quiver (so arrows
    stay readable). Sentinel-padded edges (`-1` UGRID convention) are
    filtered out.
  - `ResultControls` exposes a *Show mesh wireframe* checkbox that
    auto-disables when the open dataset has no detectable UGRID mesh.
  - `ResultPanel` caches the parsed mesh per file so toggling the
    overlay does not re-open the dataset.
- **9 new tests** (`test_mesh_adapter.py`) covering availability /
  version probes, missing-file handling, the xugrid path, the
  heuristic fallback, the `MeshGeometry` count properties and a
  full NetCDF round-trip on disk. Total: **129 tests** passing.

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

[Unreleased]: https://github.com/ghvmof/deltasuite/compare/v0.1.0a2...HEAD
[0.1.0a2]: https://github.com/ghvmof/deltasuite/compare/v0.1.0a1...v0.1.0a2
[0.1.0a1]: https://github.com/ghvmof/deltasuite/releases/tag/v0.1.0a1
