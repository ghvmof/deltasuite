"""Optional integration with Deltares' ``dfm-tools`` post-processing library.

``dfm-tools`` (https://github.com/Deltares/dfm_tools) bundles the high-level
post-processing routines that the Deltares team uses internally with
D-Flow FM and Delft3D 4 NetCDF output. Compared to using bare xarray it
gives us:

* **Partitioned dataset support** — opening MPI runs that split output
  across ``*_0000_map.nc`` / ``*_0001_map.nc`` / … files transparently.
* **Curvilinear opener** that knows about the historical Delft3D 4 layout
  (``XCOR``/``YCOR`` vs ``XZ``/``YZ``, masking from ``KCS``, etc.).
* **UGRID-aware** plot routines (``plot_netmapdata``, ``velovect``, etc.).
* **U/V helpers** for vector overlays on top of map results.

Like :mod:`deltasuite.core.hydrolib_adapter` this module never raises in
the face of a missing dependency: callers get either a real result object
or a structured "not available / failed because…" answer they can show
to the user.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:  # pragma: no cover -- import only for type checking
    import numpy as np
    import xarray as xr
    from numpy.typing import NDArray


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def is_dfm_tools_available() -> bool:
    """Return ``True`` if ``dfm-tools`` can be imported.

    ``dfm-tools`` itself takes ~30 s to import on first call (it triggers
    the ``numba`` JIT cache for ``numba_celltree``), so we only want to
    pay that cost when the user actually needs a feature it provides.
    """
    try:
        import dfm_tools  # noqa: F401

        return True
    except ImportError:
        return False


@lru_cache(maxsize=1)
def dfm_tools_version() -> str | None:
    """Return the installed ``dfm-tools`` version, or ``None``."""
    if not is_dfm_tools_available():
        return None
    try:
        import dfm_tools as dfmt

        return str(getattr(dfmt, "__version__", "unknown"))
    except Exception:  # pragma: no cover -- defensive
        return None


# ---------------------------------------------------------------------------
# Result objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DfmDatasetResult:
    """Outcome of an attempt to open a dataset with ``dfm-tools``."""

    path: Path
    dataset: xr.Dataset | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.dataset is not None


@dataclass(frozen=True, slots=True)
class UVField:
    """A pair of co-registered U / V components ready for ``quiver``.

    All four arrays share the same shape; ``mask`` is a boolean array
    where ``True`` means "no valid data here".
    """

    x: NDArray[np.floating]
    y: NDArray[np.floating]
    u: NDArray[np.floating]
    v: NDArray[np.floating]
    mask: NDArray[np.bool_]
    units: str = ""
    """Display units (e.g. ``"m/s"``)."""

    @property
    def magnitude(self) -> NDArray[np.floating]:
        """Convenience: speed = sqrt(u**2 + v**2)."""
        import numpy as np

        return np.sqrt(self.u**2 + self.v**2)


# ---------------------------------------------------------------------------
# Public API: opening datasets
# ---------------------------------------------------------------------------


def open_partitioned_smart(file_pattern: Path) -> DfmDatasetResult:
    """Open a (potentially partitioned) D-Flow FM ``*_map.nc`` set.

    ``file_pattern`` should point at one of the partitioned files (e.g.
    ``run_0000_map.nc``); ``dfm-tools`` will detect siblings and merge
    them. If the file is not actually partitioned the call is still
    valid and just opens it as a single dataset.
    """
    file_pattern = Path(file_pattern).expanduser()
    if not is_dfm_tools_available():
        return DfmDatasetResult(path=file_pattern, error="dfm-tools is not installed")
    if not file_pattern.is_file():
        return DfmDatasetResult(path=file_pattern, error=f"file not found: {file_pattern}")

    try:
        import dfm_tools as dfmt

        ds = dfmt.open_partitioned_dataset(str(file_pattern))
    except Exception as exc:
        msg = _sanitise_error(exc)
        logger.debug("dfm-tools could not open {}: {}", file_pattern, msg)
        return DfmDatasetResult(path=file_pattern, error=msg)
    return DfmDatasetResult(path=file_pattern, dataset=ds)


def open_curvilinear_smart(path: Path) -> DfmDatasetResult:
    """Open a Delft3D 4 ``trim-*.nc`` file via ``dfm-tools``.

    ``dfm-tools`` knows the historical layout (``XCOR``/``YCOR``,
    ``KCS`` masking, ``MNK`` dimensions) and produces a tidier xarray
    dataset than a bare ``xr.open_dataset`` would. Falls back through
    the standard "not installed" / "failed" channels otherwise.
    """
    path = Path(path).expanduser()
    if not is_dfm_tools_available():
        return DfmDatasetResult(path=path, error="dfm-tools is not installed")
    if not path.is_file():
        return DfmDatasetResult(path=path, error=f"file not found: {path}")

    try:
        import dfm_tools as dfmt

        ds = dfmt.open_dataset_curvilinear(str(path))
    except Exception as exc:
        msg = _sanitise_error(exc)
        logger.debug("dfm-tools could not open curvilinear {}: {}", path, msg)
        return DfmDatasetResult(path=path, error=msg)
    return DfmDatasetResult(path=path, dataset=ds)


# ---------------------------------------------------------------------------
# Public API: vector field extraction
# ---------------------------------------------------------------------------


# Variable name candidates commonly used by Delft3D 4 (curvilinear) and
# D-Flow FM (UGRID) for the depth-averaged horizontal velocity components.
_U_CANDIDATES: tuple[str, ...] = (
    "U1",
    "u",
    "ucx",
    "mesh2d_ucx",
    "mesh2d_ucxa",
)
_V_CANDIDATES: tuple[str, ...] = (
    "V1",
    "v",
    "ucy",
    "mesh2d_ucy",
    "mesh2d_ucya",
)


def find_uv_variables(dataset: xr.Dataset) -> tuple[str | None, str | None]:
    """Return ``(u_name, v_name)`` if the dataset contains a U/V pair."""
    u = next((n for n in _U_CANDIDATES if n in dataset.variables), None)
    v = next((n for n in _V_CANDIDATES if n in dataset.variables), None)
    return u, v


def extract_uv_field(
    dataset: xr.Dataset,
    *,
    time_index: int = 0,
    layer_index: int | None = None,
    stride: int = 4,
) -> UVField | None:
    """Build a :class:`UVField` from the dataset, ready for ``quiver``.

    The returned arrays are *down-sampled* by ``stride`` along each spatial
    axis so a ``quiver`` overlay does not become an unreadable hairball.
    For unstructured meshes we fall back to face centres when available.

    Returns ``None`` if no U/V pair could be located.
    """
    import numpy as np

    u_name, v_name = find_uv_variables(dataset)
    if u_name is None or v_name is None:
        return None

    u_da = dataset[u_name]
    v_da = dataset[v_name]

    # Slice to a single time step.
    if "time" in u_da.dims:
        u_da = u_da.isel(time=min(time_index, u_da.sizes.get("time", 1) - 1))
    if "time" in v_da.dims:
        v_da = v_da.isel(time=min(time_index, v_da.sizes.get("time", 1) - 1))

    # Optional vertical layer collapse: pick a layer or take the depth average.
    for vert_dim in ("KMAXOUT_RESTR", "KMAXOUT", "k", "laydim"):
        if vert_dim in u_da.dims:
            sel = layer_index if layer_index is not None else u_da.sizes[vert_dim] // 2
            u_da = u_da.isel({vert_dim: sel})
            v_da = v_da.isel({vert_dim: sel})
            break

    u_arr = np.asarray(u_da.values, dtype=float)
    v_arr = np.asarray(v_da.values, dtype=float)

    # Pull the matching X/Y coordinates.
    x, y = _resolve_xy_for_uv(dataset, u_da)
    if x is None or y is None:
        return None

    # Down-sample structured arrays.
    if u_arr.ndim == 2 and stride > 1:
        u_arr = u_arr[::stride, ::stride]
        v_arr = v_arr[::stride, ::stride]
        if x.ndim == 2:
            x = x[::stride, ::stride]
            y = y[::stride, ::stride]

    mask = ~(np.isfinite(u_arr) & np.isfinite(v_arr))
    units = str(u_da.attrs.get("units", "")).strip()
    return UVField(x=x, y=y, u=u_arr, v=v_arr, mask=mask, units=units)


def _resolve_xy_for_uv(
    dataset: xr.Dataset, u_da: xr.DataArray
) -> tuple[NDArray[np.floating] | None, NDArray[np.floating] | None]:
    """Find x/y arrays compatible with the velocity component."""
    import numpy as np

    candidates_x = (
        "XZ",
        "XCOR",
        "mesh2d_face_x",
        "x",
        "longitude",
    )
    candidates_y = (
        "YZ",
        "YCOR",
        "mesh2d_face_y",
        "y",
        "latitude",
    )

    x = next((dataset[n].values for n in candidates_x if n in dataset.variables), None)
    y = next((dataset[n].values for n in candidates_y if n in dataset.variables), None)
    if x is None or y is None:
        return None, None
    return np.asarray(x, dtype=float), np.asarray(y, dtype=float)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _sanitise_error(exc: BaseException) -> str:
    """Single-line error suitable for status-bar display."""
    msg = str(exc).strip().splitlines()[0]
    if len(msg) > 240:
        msg = msg[:237] + "…"
    return f"{type(exc).__name__}: {msg}"


__all__ = (
    "DfmDatasetResult",
    "UVField",
    "dfm_tools_version",
    "extract_uv_field",
    "find_uv_variables",
    "is_dfm_tools_available",
    "open_curvilinear_smart",
    "open_partitioned_smart",
)
