# Working with Delft3D kernels

DeltaSuite uses the official open-source Delft3D simulation kernels as the actual computational engines. The GUI orchestrates them but does not contain its own solver.

## Supported kernels

| Engine | Binary | Used for |
|---|---|---|
| Delft3D-FLOW | `d_hydro.exe` (+ `flow2d3d.dll`) | Structured-grid hydrodynamics, sediment, salinity |
| D-Flow FM | `dflowfm-cli.exe` (+ `dflowfm.dll`) | Unstructured-grid hydrodynamics |
| DIMR | `dimr.exe` | Multi-engine coupling |
| D-Waves / SWAN | `wave.exe` | Wave propagation |
| D-Water Quality | `delwaq.exe` | Water quality, ecology |
| D-Particle | `delpar.exe` | Particle tracking |
| Real-Time Control | `rtc.exe` | Hydraulic structures control |

## Launchers

Each kernel ships with a `run_*.bat` (or `run_*.sh`) script that pre-configures the DLL search path. **DeltaSuite always prefers these scripts over directly invoking the executable**, because they make sure the Intel runtime libraries and NetCDF dependencies are found at runtime.

## Compiling kernels yourself

See the [Delft3D source repository](https://github.com/Deltares/Delft3D) for instructions. After a successful build the binaries live under:

```
<source>/install_all/bin/        # if you built with -config all
<source>/install_d3d4-suite/bin/
<source>/install_fm-suite/bin/
```

DeltaSuite will scan these folders automatically.
