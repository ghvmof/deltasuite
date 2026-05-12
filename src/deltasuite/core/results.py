"""Reading Delft3D simulation results from NetCDF.

This module provides a uniform :class:`ResultDataset` abstraction over the
two NetCDF flavours the suite produces:

* **Curvilinear** — Delft3D 4 ``trim-*.nc`` files (with NetCDF output enabled
  in the ``.mdf``). Coordinates are 2-D arrays ``XCOR(M, N)`` / ``YCOR(M, N)``
  (or ``XZ`` / ``YZ`` for cell centres).
* **Unstructured** — D-Flow FM ``*_map.nc`` files following UGRID conventions
  (``mesh2d_node_x``, ``mesh2d_face_nodes``, ``mesh2d_s1``…).

The module is intentionally Qt-free so it can be unit-tested with synthetic
data and re-used from CLI scripts.

NEFIS (the historical ``trim-*.dat`` / ``.def`` pair) is **not** read here.
Either re-run with ``Filcom``/``FlNcdf`` enabled in the ``.mdf``, or convert
with the optional ``dfm-tools`` extra.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum, unique
from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING, Any

import numpy as np
import xarray as xr
from loguru import logger

if TYPE_CHECKING:
    from numpy.typing import NDArray


@unique
class GridKind(StrEnum):
    """High-level shape of the underlying mesh."""

    CURVILINEAR = "curvilinear"
    """Structured 2-D grid (Delft3D 4)."""

    UNSTRUCTURED = "unstructured"
    """UGRID 2-D mesh (D-Flow FM)."""

    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Lightweight value objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ResultVariable:
    """Description of one plottable 2-D variable."""

    name: str
    long_name: str
    units: str
    n_time: int

    @property
    def display(self) -> str:
        """User-facing label combining long name and units."""
        if self.units:
            return f"{self.long_name} [{self.units}]"
        return self.long_name


@dataclass(frozen=True, slots=True)
class Grid2D:
    """X/Y coordinate arrays for plotting.

    For curvilinear grids ``x`` and ``y`` are 2-D arrays of shape ``(M, N)``.
    For unstructured grids they are 1-D node coordinates and ``cells`` gives
    the connectivity ``(n_cells, n_max_vertices)`` (``-1`` to pad).
    """

    kind: GridKind
    x: NDArray[np.floating]
    y: NDArray[np.floating]
    cells: NDArray[np.integer] | None = None

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        """``(xmin, xmax, ymin, ymax)`` ignoring NaN entries."""
        return (
            float(np.nanmin(self.x)),
            float(np.nanmax(self.x)),
            float(np.nanmin(self.y)),
            float(np.nanmax(self.y)),
        )


@dataclass(frozen=True, slots=True)
class Field2D:
    """A single 2-D snapshot of a result variable."""

    name: str
    units: str
    values: NDArray[np.floating]
    time: datetime | None
    grid: Grid2D


# ---------------------------------------------------------------------------
# Heuristics for known Delft3D NetCDF conventions
# ---------------------------------------------------------------------------


_CURVILINEAR_X_CANDIDATES: tuple[str, ...] = ("XCOR", "XZ", "x", "lon", "longitude")
_CURVILINEAR_Y_CANDIDATES: tuple[str, ...] = ("YCOR", "YZ", "y", "lat", "latitude")
_UGRID_NODE_X_CANDIDATES: tuple[str, ...] = ("mesh2d_node_x", "node_x", "NetNode_x")
_UGRID_NODE_Y_CANDIDATES: tuple[str, ...] = ("mesh2d_node_y", "node_y", "NetNode_y")
_UGRID_FACE_NODES_CANDIDATES: tuple[str, ...] = (
    "mesh2d_face_nodes",
    "face_nodes",
    "NetElemNode",
)
_TIME_CANDIDATES: tuple[str, ...] = ("time", "Time", "TIME")


def _first_present(candidates: tuple[str, ...], obj: xr.Dataset) -> str | None:
    for name in candidates:
        if name in obj.variables or name in obj.coords:
            return name
    return None


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------


class ResultDataset:
    """Lazy NetCDF result reader.

    Use :meth:`open` as the constructor. The class is also a context manager,
    so the underlying :class:`xarray.Dataset` is properly closed::

        with ResultDataset.open(path) as ds:
            field = ds.read_field("S1", time_index=10)
    """

    def __init__(self, path: Path, dataset: xr.Dataset, kind: GridKind) -> None:
        self._path = path.resolve()
        self._ds = dataset
        self._kind = kind
        self._grid: Grid2D | None = None

    # ------------------------------------------------------------------
    # Construction / lifecycle
    # ------------------------------------------------------------------
    @classmethod
    def open(cls, path: Path) -> ResultDataset:
        """Open ``path`` and detect its grid family."""
        path = Path(path).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Not a file: {path}")
        try:
            ds = xr.open_dataset(path, decode_timedelta=True)
        except Exception as exc:
            raise OSError(f"Could not open NetCDF file {path}: {exc}") from exc

        kind = cls._detect_grid_kind(ds)
        logger.info("Opened result {} (kind={})", path.name, kind.value)
        return cls(path, ds, kind)

    def close(self) -> None:
        """Release the underlying NetCDF handle."""
        self._ds.close()

    @property
    def raw(self) -> xr.Dataset:
        """The underlying :class:`xarray.Dataset`.

        Exposed so callers can run extra analyses (vector overlays,
        cross-sections, custom aggregations) without re-opening the file.
        Treat as read-only.
        """
        return self._ds

    def __enter__(self) -> ResultDataset:
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
    def grid_kind(self) -> GridKind:
        """Whether the dataset is curvilinear, unstructured, or unknown."""
        return self._kind

    @property
    def n_time(self) -> int:
        """Number of time steps available, or 0 if the file is time-less."""
        time_name = _first_present(_TIME_CANDIDATES, self._ds)
        if time_name is None:
            return 0
        return int(self._ds.sizes.get(time_name, 0))

    @property
    def time_label(self) -> str | None:
        """Name of the time dimension, if any."""
        return _first_present(_TIME_CANDIDATES, self._ds)

    @property
    def variables(self) -> dict[str, ResultVariable]:
        """Plottable variables, keyed by their NetCDF name."""
        results: dict[str, ResultVariable] = {}
        time_name = self.time_label
        for name, var in self._ds.data_vars.items():
            if not self._is_plottable(var, time_name):
                continue
            n_time = int(var.sizes.get(time_name, 0)) if time_name else 0
            results[str(name)] = ResultVariable(
                name=str(name),
                long_name=str(var.attrs.get("long_name") or var.attrs.get("standard_name") or name),
                units=str(var.attrs.get("units", "")),
                n_time=n_time,
            )
        return results

    def time_steps(self) -> list[datetime]:
        """Return the timestamps decoded by xarray, or an empty list."""
        time_name = self.time_label
        if time_name is None:
            return []
        coord = self._ds[time_name].values
        steps: list[datetime] = []
        for value in coord:
            try:
                ts = np.datetime64(value).astype("datetime64[ms]").astype("O")
                if isinstance(ts, datetime):
                    steps.append(ts)
                else:  # pragma: no cover - cftime fallbacks
                    steps.append(datetime.fromisoformat(str(value)))
            except (TypeError, ValueError):  # pragma: no cover - exotic calendars
                steps.append(datetime.min)
        return steps

    # ------------------------------------------------------------------
    # Grid + field access
    # ------------------------------------------------------------------
    def grid(self) -> Grid2D:
        """Return the (cached) :class:`Grid2D` of this dataset."""
        if self._grid is not None:
            return self._grid
        if self._kind is GridKind.CURVILINEAR:
            self._grid = self._build_curvilinear_grid()
        elif self._kind is GridKind.UNSTRUCTURED:
            self._grid = self._build_unstructured_grid()
        else:
            raise RuntimeError(
                f"Cannot build grid: unknown coordinate convention in {self._path.name}"
            )
        return self._grid

    def read_field(self, name: str, time_index: int = 0) -> Field2D:
        """Return one snapshot of variable ``name`` at ``time_index``."""
        if name not in self._ds.data_vars:
            raise KeyError(f"Variable {name!r} not found in {self._path.name}")
        var = self._ds[name]
        time_name = self.time_label
        if time_name and time_name in var.dims:
            n = int(var.sizes[time_name])
            if not 0 <= time_index < n:
                raise IndexError(f"time_index {time_index} out of range (0..{n - 1})")
            slice_ = var.isel({time_name: time_index})
        else:
            slice_ = var

        # Squeeze degenerate dimensions (e.g. layer index with size 1).
        slice_ = slice_.squeeze(drop=True)

        values = np.asarray(slice_.values, dtype=np.float64)
        timestamp = self._timestamp_at(time_index)
        return Field2D(
            name=name,
            units=str(var.attrs.get("units", "")),
            values=values,
            time=timestamp,
            grid=self.grid(),
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    @staticmethod
    def _detect_grid_kind(ds: xr.Dataset) -> GridKind:
        if _first_present(_UGRID_NODE_X_CANDIDATES, ds) and _first_present(
            _UGRID_FACE_NODES_CANDIDATES, ds
        ):
            return GridKind.UNSTRUCTURED
        if _first_present(_CURVILINEAR_X_CANDIDATES, ds) and _first_present(
            _CURVILINEAR_Y_CANDIDATES, ds
        ):
            return GridKind.CURVILINEAR
        return GridKind.UNKNOWN

    def _build_curvilinear_grid(self) -> Grid2D:
        x_name = _first_present(_CURVILINEAR_X_CANDIDATES, self._ds)
        y_name = _first_present(_CURVILINEAR_Y_CANDIDATES, self._ds)
        assert x_name is not None
        assert y_name is not None
        x = np.asarray(self._ds[x_name].values, dtype=np.float64)
        y = np.asarray(self._ds[y_name].values, dtype=np.float64)
        if x.ndim == 1 and y.ndim == 1:
            xx, yy = np.meshgrid(x, y, indexing="xy")
            x, y = xx, yy
        return Grid2D(kind=GridKind.CURVILINEAR, x=x, y=y)

    def _build_unstructured_grid(self) -> Grid2D:
        x_name = _first_present(_UGRID_NODE_X_CANDIDATES, self._ds)
        y_name = _first_present(_UGRID_NODE_Y_CANDIDATES, self._ds)
        face_name = _first_present(_UGRID_FACE_NODES_CANDIDATES, self._ds)
        assert x_name is not None
        assert y_name is not None
        assert face_name is not None
        x = np.asarray(self._ds[x_name].values, dtype=np.float64)
        y = np.asarray(self._ds[y_name].values, dtype=np.float64)
        cells = np.asarray(self._ds[face_name].values, dtype=np.int64)
        # UGRID uses 1-based indexing with a fill value; normalise to 0-based.
        fill_value = self._ds[face_name].attrs.get("_FillValue")
        cells = cells - 1
        if fill_value is not None:
            cells = np.where(cells == int(fill_value) - 1, -1, cells)
        return Grid2D(kind=GridKind.UNSTRUCTURED, x=x, y=y, cells=cells)

    def _timestamp_at(self, index: int) -> datetime | None:
        time_name = self.time_label
        if time_name is None:
            return None
        try:
            value = self._ds[time_name].values[index]
        except (IndexError, KeyError):
            return None
        try:
            ts = np.datetime64(value).astype("datetime64[ms]").astype("O")
        except (TypeError, ValueError):
            return None
        return ts if isinstance(ts, datetime) else None

    @staticmethod
    def _is_plottable(var: xr.DataArray, time_name: str | None) -> bool:
        """Heuristic: a variable is plottable when reducing to 2 spatial dims."""
        spatial_dims = [d for d in var.dims if d != time_name]
        # Allow extra layer dims of size 1 (typical for sigma layer 1 only).
        sized = [d for d in spatial_dims if int(var.sizes[d]) > 1]
        return len(sized) == 2 and np.issubdtype(var.dtype, np.number)


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------


_RESULT_PATTERNS: tuple[str, ...] = (
    "trim-*.nc",
    "trih-*.nc",
    "*_map.nc",
    "*_his.nc",
    "*_com.nc",
    "*_clm.nc",
    "*.nc",
)


@dataclass(frozen=True, slots=True)
class ResultFile:
    """A NetCDF result file discovered next to a project."""

    path: Path
    role: str
    """``"map"``, ``"his"``, ``"com"``, ``"trim"``, ``"trih"`` or ``"unknown"``."""

    @property
    def is_spatial_field(self) -> bool:
        """``True`` for files that contain 2-D map snapshots over time."""
        return self.role in {"map", "trim", "com"}


def find_result_files(project_root: Path) -> list[ResultFile]:
    """Locate NetCDF result files inside ``project_root`` (non-recursive)."""
    project_root = Path(project_root).expanduser().resolve()
    if not project_root.is_dir():
        return []

    seen: set[Path] = set()
    found: list[ResultFile] = []
    for pattern in _RESULT_PATTERNS:
        for candidate in sorted(project_root.glob(pattern)):
            if candidate in seen or not candidate.is_file():
                continue
            seen.add(candidate)
            found.append(ResultFile(path=candidate, role=_classify_result(candidate)))
    return found


def _classify_result(path: Path) -> str:
    name = path.name.lower()
    if "_map" in name:
        return "map"
    if "_his" in name:
        return "his"
    if "_com" in name:
        return "com"
    if name.startswith("trim-"):
        return "trim"
    if name.startswith("trih-"):
        return "trih"
    return "unknown"


__all__: tuple[Any, ...] = (
    "Field2D",
    "Grid2D",
    "GridKind",
    "ResultDataset",
    "ResultFile",
    "ResultVariable",
    "find_result_files",
)
