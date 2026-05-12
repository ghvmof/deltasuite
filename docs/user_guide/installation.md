# Installation

DeltaSuite supports Windows, Linux and macOS. Python 3.11 or later is required.

## From source (development)

```bash
git clone https://github.com/ghvmof/deltasuite.git
cd DeltaSuite

python -m venv .venv
.venv\Scripts\activate              # Windows
# source .venv/bin/activate         # Linux / macOS

pip install -e .[dev,viz,science,delft3d]
```

## Using ``uv`` (faster)

```bash
uv venv
uv pip install -e .[dev,viz,science,delft3d]
```

## Optional dependency groups

| Group | Adds | Use it when… |
|---|---|---|
| `viz` | matplotlib, pyvista, vtk, pyqtgraph | You want 2D/3D visualization |
| `gis` | shapely, geopandas, fiona, pyproj, contextily | You need GIS support |
| `science` | xarray, xugrid, netCDF4, scipy, pandas | You will work with NetCDF outputs |
| `delft3d` | hydrolib-core, dfm-tools, meshkernel | You will use the Deltares Python ecosystem |
| `dev` | pytest, ruff, mypy, pytest-qt | Contributing |
| `docs` | sphinx, sphinx-rtd-theme, myst-parser | Building docs |
| `build` | pyinstaller, hatchling | Packaging installers |

The convenience meta-group `[all]` installs `viz + gis + science + delft3d`.

## Delft3D simulation kernels

DeltaSuite invokes the official Delft3D engines as subprocesses. They are **not** bundled. Install them by either:

- Compiling from source: see [Deltares/Delft3D on GitHub](https://github.com/Deltares/Delft3D).
- Installing the official Deltares Service Pack.
- Setting `DELTASUITE_KERNEL_DIR` to your `install_*/bin` folder.

DeltaSuite auto-detects common locations on first launch.
