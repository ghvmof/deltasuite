# Visualising results

DeltaSuite reads simulation outputs in NetCDF format. Two flavours are
supported out of the box:

| Format                                       | Source kernel | Conventions               |
| -------------------------------------------- | ------------- | ------------------------- |
| `trim-<runid>.nc`, `trih-<runid>.nc`         | Delft3D 4     | Curvilinear `XCOR / YCOR` |
| `<modelname>_map.nc`, `<modelname>_his.nc`   | D-Flow FM     | UGRID `mesh2d_*`          |

> **NEFIS files** (`trim-*.dat` + `.def`) are not read directly. Re-run
> with NetCDF output enabled in the `.mdf` (set `Filcom = #YES#` and
> `FlNcdf = trim`), or convert with the optional `dfm-tools` extra.

## The Map tab

When a project is opened (or after a successful simulation), the **Map**
tab in the central area is populated automatically:

- The file selector lists every NetCDF found at the project root.
- The variable selector lists every plottable 2-D variable, with units.
- The time slider scrubs through the simulation steps; the timestamp is
  shown above it.
- The colormap drop-down switches between Matplotlib's perceptually
  uniform colormaps.
- The **Auto** checkbox toggles between automatic (1-99 percentile) and
  fixed colour ranges.

The Matplotlib navigation toolbar (top of the canvas) provides pan / zoom
/ home / save-to-PNG actions identical to a desktop Matplotlib window.

## Opening a NetCDF without a project

Use **File → Open Result File…** (`Ctrl+R`) and pick any `.nc` file. The
*Map* tab opens with that single file selected.

## Programmatic access

For scripting, use [`deltasuite.core.results.ResultDataset`][api]:

```python
from deltasuite.core import ResultDataset

with ResultDataset.open("trim-myrun.nc") as ds:
    print(list(ds.variables))                # available fields
    print(ds.time_steps())                   # decoded timestamps
    field = ds.read_field("S1", time_index=10)
    field.values         # np.ndarray (M, N)
    field.grid           # Grid2D, includes x/y coords
```

[api]: https://deltasuite.readthedocs.io/  "API reference"
