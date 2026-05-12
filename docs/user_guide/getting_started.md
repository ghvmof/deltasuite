# Getting started

After [installing](installation.md) DeltaSuite, launch the GUI:

```bash
deltasuite
```

You should see the welcome screen.

## Detecting Delft3D kernels

From the command line:

```bash
deltasuite detect
```

Or from inside the GUI: **Run → Detect Delft3D kernels…**

DeltaSuite looks in:

1. Paths configured under Preferences (later phases)
2. The `DELTASUITE_KERNEL_DIR` environment variable
3. `install_*/bin` folders under typical development roots
4. The Deltares Service Pack installation in `Program Files`
5. The system `PATH`

## Creating your first project

1. **File → New Project…** — choose an empty directory.
2. DeltaSuite will create a `deltasuite.toml` file describing the project.
3. Drop your model input files (`.mdf`, `.mdu`, etc.) into the project directory.
4. Use the **Run** menu to launch the simulation (available in Phase 1).

## Browsing existing examples

If you already have the official Delft3D `examples/` folder (or any other
collection of models), use **File → Browse Models in Folder…** (`Ctrl+B`).
DeltaSuite recursively scans the chosen directory and presents a chooser
with every project it finds — pick one and it is opened immediately.

## Visualising results

Whenever a project is open or a simulation finishes, DeltaSuite scans the
project root for NetCDF outputs (Delft3D 4 `trim-*.nc` and D-Flow FM
`*_map.nc`). The **Map** tab in the workspace shows them with:

- a Matplotlib viewer (full pan / zoom / save toolbar),
- a side panel to switch file, variable, time step and colormap,
- automatic colour range based on the 1–99 percentile, with a manual
  override.

You can also use **File → Open Result File… (`Ctrl+R`)** to open any NetCDF
file independently of a project.

## Where things live

| Item | Default location |
|---|---|
| Settings | `%APPDATA%\DeltaSuite\settings.toml` (Windows) |
| Logs | `%LOCALAPPDATA%\DeltaSuite\Logs\deltasuite.log` (Windows) |
| Cache | OS-specific cache directory |
