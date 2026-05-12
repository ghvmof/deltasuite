# Visualising time series

History NetCDFs (Delft3D 4 `trih-*.nc` and D-Flow FM `*_his.nc`) store
time series at named monitoring stations. The **Series** tab in the
DeltaSuite workspace renders them as overlay line plots.

## File formats

| Format         | Source kernel | Conventions                              |
| -------------- | ------------- | ---------------------------------------- |
| `trih-*.nc`    | Delft3D 4     | `NOSTAT` dim + `NAMST(NOSTAT, 20)` chars |
| `*_his.nc`     | D-Flow FM     | `stations` dim + `station_name` strings  |

NEFIS history pairs are not read directly; export to NetCDF first or use
the optional `dfm-tools` extra.

## The Series tab

When a project is opened (or after a successful simulation) DeltaSuite
scans the project root for history files and populates the **Series** tab
automatically. The control panel offers:

- **File** — switch between several `*_his.nc` / `trih-*.nc`
  outputs;
- **Variable** — every plottable scalar with its long name and units;
- **Stations** — multi-select list with **All** / **None** shortcuts;
- **Export CSV…** — write the visible curves to a single CSV file with
  one column per station (time first).

The matplotlib navigation toolbar (top of the chart) provides
pan / zoom / home / save-as-PNG actions.

## Open a NetCDF without a project

Use **File → Open Time-series File…** (`Ctrl+T`).

## Programmatic access

```python
from deltasuite.core import TimeSeriesDataset

with TimeSeriesDataset.open("case_his.nc") as ds:
    print(ds.stations)
    series = ds.read_many("waterlevel", ds.stations[:3])
    for s in series:
        print(s.station, s.values.mean())
```
