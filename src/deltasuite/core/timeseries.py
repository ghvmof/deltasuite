"""Reading time series from Delft3D ``*_his.nc`` and ``trih-*.nc`` files.

A *history* file stores model variables sampled at named monitoring stations,
cross sections or observation points. Compared to the map files handled by
:mod:`deltasuite.core.results`, the spatial dimension is reduced to a 1-D
list of named locations, so the natural visualisation is a multi-line plot.

Two flavours are recognised:

* **Delft3D 4** ``trih-<runid>.nc`` — variables like ``ZWL`` (water level at
  observation points) with dim ``NOSTAT`` and a sibling ``NAMST(NOSTAT, 20)``
  giving station names as fixed-length character arrays.
* **D-Flow FM** ``*_his.nc`` — variables like ``waterlevel`` with dim
  ``stations`` and either ``station_name`` or ``stations`` coordinate
  variables.

NEFIS history files are not read here; export to NetCDF first or use the
optional ``dfm-tools`` extra.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING

import numpy as np
import xarray as xr
from loguru import logger

if TYPE_CHECKING:
    from numpy.typing import NDArray


_TIME_CANDIDATES: tuple[str, ...] = ("time", "Time", "TIME")
_STATION_DIM_CANDIDATES: tuple[str, ...] = (
    "stations",
    "station",
    "NOSTAT",
    "nostat",
    "name_len",
)
_STATION_NAME_CANDIDATES: tuple[str, ...] = (
    "station_name",
    "stations",
    "NAMST",
    "namst",
)
_PATTERNS: tuple[str, ...] = ("*_his.nc", "trih-*.nc")


@dataclass(frozen=True, slots=True)
class TimeSeriesVariable:
    """A scalar variable available at every monitoring location."""

    name: str
    long_name: str
    units: str
    n_time: int
    n_stations: int

    @property
    def display(self) -> str:
        """User-facing label combining long name and units."""
        if self.units:
            return f"{self.long_name} [{self.units}]"
        return self.long_name


@dataclass(frozen=True, slots=True)
class StationSeries:
    """One station's time series for a given variable."""

    station: str
    variable: str
    units: str
    times: NDArray[np.datetime64]
    values: NDArray[np.floating]


def _first_present(candidates: tuple[str, ...], obj: xr.Dataset) -> str | None:
    for name in candidates:
        if name in obj.variables or name in obj.coords or name in obj.dims:
            return name
    return None


def _decode_station_names(arr: xr.DataArray) -> list[str]:
    """Decode an xarray of station labels (string or char-array) to ``list[str]``."""
    values = arr.values
    if values.ndim == 1:
        return [_normalise_label(item) for item in values.tolist()]
    if values.ndim == 2:
        # Char array layout used by Delft3D 4 (NOSTAT, name_len).
        names: list[str] = []
        for row in values:
            if row.dtype.kind in ("S", "a"):
                names.append(row.tobytes().decode("utf-8", errors="replace").strip())
            else:
                names.append("".join(str(c) for c in row).strip())
        return names
    return [str(values).strip()]


def _normalise_label(item: object) -> str:
    if isinstance(item, bytes):
        return item.decode("utf-8", errors="replace").strip()
    return str(item).strip()


class TimeSeriesDataset:
    """Lazy reader for a single ``*_his.nc`` or ``trih-*.nc`` file.

    Use :meth:`open` as the constructor; it doubles as a context manager so
    the underlying :class:`xarray.Dataset` is closed deterministically::

        with TimeSeriesDataset.open(path) as ds:
            series = ds.read_series("waterlevel", "Station_01")
    """

    def __init__(
        self,
        path: Path,
        dataset: xr.Dataset,
        station_dim: str | None,
        time_dim: str | None,
        stations: list[str],
    ) -> None:
        self._path = path.resolve()
        self._ds = dataset
        self._station_dim = station_dim
        self._time_dim = time_dim
        self._stations = stations

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    @classmethod
    def open(cls, path: Path) -> TimeSeriesDataset:
        """Open ``path`` and discover its station/time conventions."""
        path = Path(path).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Not a file: {path}")
        try:
            ds = xr.open_dataset(path, decode_timedelta=True)
        except Exception as exc:
            raise OSError(f"Could not open NetCDF file {path}: {exc}") from exc

        station_dim = cls._detect_station_dim(ds)
        time_dim = _first_present(_TIME_CANDIDATES, ds)
        stations = cls._extract_station_names(ds, station_dim)
        logger.info(
            "Opened time-series {} (stations={}, time_dim={})",
            path.name,
            len(stations),
            time_dim,
        )
        return cls(path, ds, station_dim, time_dim, stations)

    def close(self) -> None:
        """Release the underlying NetCDF handle."""
        self._ds.close()

    def __enter__(self) -> TimeSeriesDataset:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------
    @property
    def path(self) -> Path:
        """Absolute path of the source NetCDF file."""
        return self._path

    @property
    def stations(self) -> list[str]:
        """Decoded station labels in the order the file declares them."""
        return list(self._stations)

    @property
    def n_stations(self) -> int:
        """Number of stations (``0`` for files without a station dimension)."""
        return len(self._stations)

    @property
    def time_dim(self) -> str | None:
        """Name of the time dimension."""
        return self._time_dim

    @property
    def station_dim(self) -> str | None:
        """Name of the station dimension (or ``None`` if the file lacks one)."""
        return self._station_dim

    @property
    def variables(self) -> dict[str, TimeSeriesVariable]:
        """Plottable variables, keyed by their NetCDF name."""
        results: dict[str, TimeSeriesVariable] = {}
        for name, var in self._ds.data_vars.items():
            if not self._is_plottable(var):
                continue
            n_time = int(var.sizes.get(self._time_dim, 0)) if self._time_dim else 0
            n_st = int(var.sizes.get(self._station_dim, 0)) if self._station_dim else 0
            results[str(name)] = TimeSeriesVariable(
                name=str(name),
                long_name=str(var.attrs.get("long_name") or var.attrs.get("standard_name") or name),
                units=str(var.attrs.get("units", "")),
                n_time=n_time,
                n_stations=n_st,
            )
        return results

    def time_steps(self) -> NDArray[np.datetime64]:
        """Decoded time array, or an empty array if the file is time-less."""
        if self._time_dim is None:
            return np.empty(0, dtype="datetime64[ns]")
        return np.asarray(self._ds[self._time_dim].values, dtype="datetime64[ns]")

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------
    def read_series(self, variable: str, station: str) -> StationSeries:
        """Return the time series of ``variable`` at ``station``."""
        if variable not in self._ds.data_vars:
            raise KeyError(f"Variable {variable!r} not found in {self._path.name}")
        if station not in self._stations:
            raise KeyError(f"Station {station!r} not found in {self._path.name}")
        idx = self._stations.index(station)
        var = self._ds[variable]

        slice_ = var
        if self._station_dim and self._station_dim in var.dims:
            slice_ = slice_.isel({self._station_dim: idx})
        slice_ = slice_.squeeze(drop=True)

        values = np.asarray(slice_.values, dtype=np.float64)
        return StationSeries(
            station=station,
            variable=variable,
            units=str(var.attrs.get("units", "")),
            times=self.time_steps(),
            values=values,
        )

    def read_many(self, variable: str, stations: list[str]) -> list[StationSeries]:
        """Convenience: :meth:`read_series` over multiple stations."""
        return [self.read_series(variable, st) for st in stations]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    @staticmethod
    def _detect_station_dim(ds: xr.Dataset) -> str | None:
        for name in _STATION_DIM_CANDIDATES:
            if name in ds.dims:
                return name
        return None

    @classmethod
    def _extract_station_names(cls, ds: xr.Dataset, station_dim: str | None) -> list[str]:
        if station_dim is None:
            return []
        # Prefer an explicit name variable.
        for candidate in _STATION_NAME_CANDIDATES:
            if candidate in ds.variables and candidate != station_dim:
                names = _decode_station_names(ds[candidate])
                if len(names) >= ds.sizes[station_dim]:
                    return names[: ds.sizes[station_dim]]
        # Fall back to numeric labels.
        return [f"station_{i + 1}" for i in range(ds.sizes[station_dim])]

    def _is_plottable(self, var: xr.DataArray) -> bool:
        if not np.issubdtype(var.dtype, np.number):
            return False
        if self._time_dim and self._time_dim not in var.dims:
            return False
        if self._station_dim and self._station_dim not in var.dims:
            return False
        # Reject variables with extra non-singleton dims (e.g. layered output).
        extra_dims = [
            d
            for d in var.dims
            if d not in {self._time_dim, self._station_dim} and int(var.sizes[d]) > 1
        ]
        return not extra_dims


@dataclass(frozen=True, slots=True)
class TimeSeriesFile:
    """A history NetCDF file discovered next to a project."""

    path: Path
    role: str
    """``"his"`` (D-Flow FM) or ``"trih"`` (Delft3D 4)."""


def find_history_files(project_root: Path) -> list[TimeSeriesFile]:
    """Locate NetCDF history files inside ``project_root`` (non-recursive)."""
    project_root = Path(project_root).expanduser().resolve()
    if not project_root.is_dir():
        return []

    seen: set[Path] = set()
    found: list[TimeSeriesFile] = []
    for pattern in _PATTERNS:
        for candidate in sorted(project_root.glob(pattern)):
            if candidate in seen or not candidate.is_file():
                continue
            seen.add(candidate)
            role = "trih" if candidate.name.lower().startswith("trih-") else "his"
            found.append(TimeSeriesFile(path=candidate, role=role))
    return found


__all__ = (
    "StationSeries",
    "TimeSeriesDataset",
    "TimeSeriesFile",
    "TimeSeriesVariable",
    "find_history_files",
)
