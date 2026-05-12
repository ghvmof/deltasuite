<div align="center">

# DeltaSuite

**Open source desktop suite for pre-processing, running and post-processing Delft3D models.**

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Status](https://img.shields.io/badge/status-pre--alpha-orange)]()

</div>

---

DeltaSuite is a free, open-source desktop application that provides a modern, intuitive graphical interface to the [Delft3D](https://oss.deltares.nl/web/delft3d) and [Delft3D FM](https://oss.deltares.nl/web/delft3dfm) modeling suites developed by [Deltares](https://www.deltares.nl/en).

It is built on the official Deltares Python ecosystem (`hydrolib-core`, `dfm_tools`, `MeshKernel`) and the open-source Delft3D simulation kernels, providing a unified workspace for hydrodynamic, morphological, water-quality and wave modeling.

> **Status:** Pre-alpha. Active development. Not yet recommended for production use.

## Vision

To provide the scientific and engineering community with a single, free, professional-grade desktop application that covers the complete Delft3D workflow:

- **Pre-processing:** mesh generation, bathymetry interpolation, boundary conditions, model setup
- **Simulation:** running the open-source Delft3D kernels with real-time monitoring
- **Post-processing:** 2D/3D visualization, time series analysis, validation against observations
- **Multi-module:** unified interface for FLOW, D-Flow FM, WAQ, WAVE, PART and RTC

## Features (planned for v1.0)

- [x] Project explorer with auto-save and version control friendly file format
- [x] Recursive project discovery (Browse Models in Folder…)
- [x] Configuration editors for `.mdf` (Delft3D 4) and `.mdu` (D-Flow FM)
- [x] Real-time simulation runner with log streaming and progress
- [x] 2D result viewer for `trim/trih` and NetCDF outputs (curvilinear + UGRID)
- [x] Time-series viewer for `*_his.nc` / `trih-*.nc` with CSV export
- [ ] 3D mesh viewer (curvilinear and unstructured)
- [ ] Bathymetry editor with interpolation tools
- [ ] Boundary condition editor with map preview
- [ ] Vertical profile plots
- [ ] WAQ substance and process editor
- [ ] SWAN wave model integration
- [ ] DIMR coupling support (FLOW-WAVE, FLOW-RTC)
- [ ] Plugin system for community extensions
- [ ] Multi-language UI (English, Spanish initially)

## Requirements

- Python 3.11 or later
- Qt 6 (installed via PySide6)
- A working Delft3D installation. The simulation kernels can be obtained by:
  - Compiling from source: see [Deltares/Delft3D](https://github.com/Deltares/Delft3D)
  - Installing the official Deltares Service Package
  - DeltaSuite will auto-detect installations or you can configure paths manually.

## Installation

### From source (development)

```bash
git clone https://github.com/ghvmof/deltasuite.git
cd deltasuite
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux / Mac
pip install -e .[dev,viz,science,delft3d]
```

### Run

```bash
deltasuite                # Launch the GUI
deltasuite-detect         # Detect installed Delft3D kernels
```

## Project layout

```
DeltaSuite/
├── src/deltasuite/         Main package
│   ├── app/                Qt application and main window
│   ├── cli/                Command-line entry points
│   ├── core/               Domain models and project management
│   ├── editors/            Property editors (boundaries, physics, output, ...)
│   ├── io/                 Readers/writers for .mdf, .mdu, .grd, .dep, NetCDF
│   ├── mesh/               Mesh generation and editing (via MeshKernel)
│   ├── modules/            Wrappers for FLOW, FM, WAQ, WAVE, PART, RTC
│   ├── views/              2D/3D viewers
│   ├── widgets/            Reusable Qt widgets
│   └── resources/          Icons, themes, translations
├── tests/                  pytest test suite
├── docs/                   Sphinx documentation
├── installer/              Build scripts for installers (PyInstaller, Inno Setup)
└── .github/workflows/      Continuous integration
```

## Development

DeltaSuite uses modern Python tooling:

- **[Hatchling](https://hatch.pypa.io/)** as the build backend
- **[Ruff](https://docs.astral.sh/ruff/)** for linting and formatting
- **[Mypy](https://mypy.readthedocs.io/)** for static type checking
- **[Pytest](https://docs.pytest.org/)** + **[pytest-qt](https://pytest-qt.readthedocs.io/)** for testing
- **[Sphinx](https://www.sphinx-doc.org/)** for documentation
- **[GitHub Actions](https://github.com/features/actions)** for CI/CD

Common commands:

```bash
ruff check .              # Lint
ruff format .             # Format code
mypy src                  # Type check
pytest                    # Run tests
sphinx-build docs docs/_build/html   # Build docs
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## License

DeltaSuite is licensed under the **GNU General Public License v3.0 or later**. See [LICENSE](LICENSE) for the full text.

This project links with the Delft3D simulation kernels which are licensed under GPL-3.0 / AGPL-3.0. Please respect the licenses of all bundled and linked components.

## Acknowledgments

DeltaSuite would not exist without the work of:

- **[Deltares](https://www.deltares.nl/en)** for developing and open-sourcing Delft3D, MeshKernel, hydrolib-core and dfm_tools
- **[The Qt Project](https://www.qt.io)** for the Qt framework
- **[VTK](https://vtk.org)** and **[PyVista](https://pyvista.org)** for scientific visualization
- The wider scientific Python community

## Support and community

- **Bugs and feature requests:** [GitHub Issues](https://github.com/ghvmof/deltasuite/issues)
- **Discussions:** [GitHub Discussions](https://github.com/ghvmof/deltasuite/discussions)
- **Documentation:** [deltasuite.readthedocs.io](https://deltasuite.readthedocs.io)

---

<div align="center">
<sub>Built with love for the open hydrodynamic modeling community.</sub>
</div>
