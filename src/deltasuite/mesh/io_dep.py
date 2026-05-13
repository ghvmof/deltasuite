"""Reader / writer for the legacy Delft3D ``.dep`` depth-samples format.

Why this exists
---------------
A Delft3D 4 project ships its bathymetry as a plain-text ``.dep`` file
that lives next to the ``.grd`` mesh and the ``.enc`` enclosure. To
let DeltaSuite render *real* topographies in the Map and 3D tabs --
instead of the demo extrusion -- we need a self-contained parser
that aligns those samples with our :class:`MeshGeometry`.

File layout (Delft3D-FLOW)
--------------------------
The file is a flat block of floating-point values written row-major,
with twelve numbers per line by convention (the parser is tolerant)
and a sentinel for inactive cells -- either decimal ``-999.000`` or
scientific ``-9.99E+02``. Three layouts coexist in real projects:

* ``corners_extra`` (DPV, the most common): ``(N+1) x (M+1)`` values,
  i.e. one extra row and one extra column compared to the ``M x N``
  grid; the last row and column are sentinels and are dropped on
  load.
* ``nodes``: exactly ``M x N`` values, aligned one-to-one with the
  grid nodes.
* ``centers`` (zeta points): ``(M-1) x (N-1)`` values living at the
  cell centres. We refuse these for now -- there is no lossless
  mapping to per-node values without interpolation.

The parser auto-detects the layout from the file size and the mesh's
``structured_shape``, so callers don't have to care. The writer
always emits the canonical ``corners_extra`` layout, which is what
RGFGRID and FLOW2D3D both accept.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
from loguru import logger

from deltasuite.core.mesh_adapter import MeshGeometry

DEFAULT_MISSING_VALUE = -999.0
"""Canonical Delft3D 4 sentinel; nodes within ``MISSING_TOLERANCE`` of
this value (or of any explicit ``missing_value`` passed in) are treated
as inactive on load and serialised back to it on save."""

MISSING_TOLERANCE = 1e-3
"""Numeric tolerance used when comparing a sample to the missing
sentinel. Real ``.dep`` files use ``-999.000`` *or* the slightly more
precise ``-9.99999E+02``; both must be recognised."""

_VALUES_PER_LINE = 12

DepthLayout = Literal["corners_extra", "nodes", "centers"]


@dataclass(frozen=True, slots=True)
class DepthField:
    """Per-node bathymetry aligned with a structured :class:`MeshGeometry`.

    ``node_values`` is a 1-D float64 array of length ``mesh.n_nodes``.
    Missing samples are stored as :data:`numpy.nan` so downstream code
    can simply mask them with :func:`numpy.isnan`. ``missing_value``
    and ``layout`` are kept for diagnostics and to enable a faithful
    round-trip on save.
    """

    node_values: np.ndarray  # shape (n_nodes,), dtype float64
    missing_value: float
    layout: DepthLayout

    @property
    def n_nodes(self) -> int:
        return int(self.node_values.size)

    @property
    def n_valid(self) -> int:
        return int(np.sum(~np.isnan(self.node_values)))

    @property
    def n_missing(self) -> int:
        return self.n_nodes - self.n_valid

    @property
    def value_range(self) -> tuple[float, float]:
        """``(min, max)`` over the *valid* (non-NaN) samples."""
        valid = self.node_values[~np.isnan(self.node_values)]
        if valid.size == 0:
            return (0.0, 0.0)
        return (float(valid.min()), float(valid.max()))


@dataclass(frozen=True, slots=True)
class DepthLoadResult:
    """Wrapper returned by :func:`load_dep_samples`."""

    path: Path
    field: DepthField | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.field is not None


# ---------------------------------------------------------------------------
# Reader
# ---------------------------------------------------------------------------


def load_dep_samples(
    path: Path | str,
    mesh: MeshGeometry,
    *,
    missing_value: float = DEFAULT_MISSING_VALUE,
) -> DepthLoadResult:
    """Parse a Delft3D ``.dep`` file and align it to ``mesh``.

    The mesh **must** carry a ``structured_shape``; that is the only
    way we know how to fold the flat sample list back into a 2-D
    array. UGRID meshes (triangulations, refined meshes) are rejected
    with a clear error -- they need a different ingestion path
    (``samples + spatial-search`` interpolation).
    """
    file_path = Path(path).expanduser()
    if not file_path.exists():
        return DepthLoadResult(path=file_path, error=f"file not found: {file_path}")
    if mesh.structured_shape is None:
        return DepthLoadResult(
            path=file_path,
            error="depth import requires a structured mesh (load a .grd first)",
        )

    try:
        text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = file_path.read_text(encoding="latin-1")

    try:
        field = _parse_dep_text(text, mesh, missing_value=missing_value)
    except ValueError as exc:
        logger.warning("Could not parse {} as Delft3D .dep: {}", file_path, exc)
        return DepthLoadResult(path=file_path, error=f"ValueError: {exc}")
    return DepthLoadResult(path=file_path, field=field)


def _parse_dep_text(
    text: str,
    mesh: MeshGeometry,
    *,
    missing_value: float,
) -> DepthField:
    assert mesh.structured_shape is not None  # guarded by caller
    n_rows, n_cols = mesh.structured_shape

    values = _floats_in(text)
    if values.size == 0:
        raise ValueError("file contains no numeric samples")

    layout, grid = _reshape_to_layout(values, n_rows, n_cols)

    grid = grid.astype(np.float64, copy=False)
    grid = np.where(_is_missing(grid, missing_value), np.nan, grid)

    if layout == "centers":
        # Refused early in _reshape_to_layout, but kept here for
        # completeness in case we add interpolation later.
        raise ValueError("cell-centred (.dep) layouts are not supported yet")

    if layout == "corners_extra":
        # The last row and last column are sentinels -- drop them.
        grid = grid[:n_rows, :n_cols]

    if grid.shape != (n_rows, n_cols):  # pragma: no cover -- defensive
        raise ValueError(f"internal layout mismatch: got {grid.shape}, expected {(n_rows, n_cols)}")

    node_values = grid.ravel().astype(np.float64, copy=False)
    return DepthField(
        node_values=node_values,
        missing_value=float(missing_value),
        layout=layout,
    )


def _reshape_to_layout(
    values: np.ndarray, n_rows: int, n_cols: int
) -> tuple[DepthLayout, np.ndarray]:
    """Return ``(layout_tag, 2-D array)`` matching the mesh shape.

    Tries the three documented Delft3D layouts in decreasing order of
    real-world prevalence (DPV first, then node-aligned, then centres
    -- which we refuse). Raises :class:`ValueError` with a friendly
    message if none of them fit.
    """
    n_total = values.size
    candidates: list[tuple[DepthLayout, int, int]] = [
        ("corners_extra", n_rows + 1, n_cols + 1),
        ("nodes", n_rows, n_cols),
        ("centers", n_rows - 1, n_cols - 1),
    ]
    for layout, rows, cols in candidates:
        if rows <= 0 or cols <= 0:
            continue
        if rows * cols != n_total:
            continue
        if layout == "centers":
            raise ValueError(
                f"file holds {rows}x{cols} cell-centre samples; node-centred layout required"
            )
        return layout, values.reshape(rows, cols)
    expected = ", ".join(f"{rows}x{cols}={rows * cols}" for _, rows, cols in candidates if rows > 0)
    raise ValueError(
        f"sample count {n_total} does not match any expected layout for a "
        f"{n_rows}x{n_cols} mesh (tried {expected})"
    )


def _floats_in(text: str) -> np.ndarray:
    """Stream every numeric token in ``text`` as a 1-D float64 array."""
    out: list[float] = []
    for token in text.split():
        try:
            out.append(float(token))
        except ValueError:
            # Tolerate stray annotations like ``***`` markers
            continue
    return np.asarray(out, dtype=np.float64)


def _is_missing(values: np.ndarray, missing_value: float) -> np.ndarray:
    """Return a boolean mask where ``values`` are within tolerance of
    the missing sentinel."""
    diff = np.abs(values - missing_value)
    return np.asarray(diff <= MISSING_TOLERANCE, dtype=bool)


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------


def save_dep_samples(
    field: DepthField,
    path: Path | str,
    mesh: MeshGeometry,
    *,
    missing_value: float = DEFAULT_MISSING_VALUE,
    overwrite: bool = True,
) -> DepthLoadResult:
    """Serialise ``field`` to ``path`` in canonical Delft3D ``.dep`` form.

    The output always uses the ``corners_extra`` layout (the most
    portable choice -- both RGFGRID and FLOW2D3D consume it),
    twelve values per line, with NaN samples written as
    ``missing_value`` and the trailing sentinel row/column appended
    automatically.
    """
    target = Path(path).expanduser()
    if target.exists() and not overwrite:
        return DepthLoadResult(path=target, error=f"target already exists: {target}")
    if mesh.structured_shape is None:
        return DepthLoadResult(
            path=target,
            error="depth export requires a structured mesh (round-trip via .grd first)",
        )

    n_rows, n_cols = mesh.structured_shape
    if field.node_values.size != n_rows * n_cols:
        return DepthLoadResult(
            path=target,
            error=(
                f"depth length {field.node_values.size} does not match "
                f"mesh node count {n_rows * n_cols}"
            ),
        )

    grid = np.asarray(field.node_values, dtype=np.float64).reshape(n_rows, n_cols)
    out = np.full((n_rows + 1, n_cols + 1), missing_value, dtype=np.float64)
    out[:n_rows, :n_cols] = np.where(np.isnan(grid), missing_value, grid)

    text = _format_dep(out)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.write_text(text, encoding="utf-8")
    except OSError as exc:  # pragma: no cover -- defensive
        return DepthLoadResult(path=target, error=f"OSError: {exc}")

    return DepthLoadResult(
        path=target,
        field=DepthField(
            node_values=field.node_values.astype(np.float64, copy=False),
            missing_value=float(missing_value),
            layout="corners_extra",
        ),
    )


def _format_dep(grid: np.ndarray) -> str:
    """Serialise ``grid`` (already including the sentinel row/col) as
    twelve scientific-notation values per line, mimicking RGFGRID's
    own output."""
    lines: list[str] = []
    for row in grid:
        for start in range(0, row.size, _VALUES_PER_LINE):
            chunk = row[start : start + _VALUES_PER_LINE]
            lines.append("".join(f"{value:16.7E}" for value in chunk))
    return "\n".join(lines) + "\n"


__all__ = (
    "DEFAULT_MISSING_VALUE",
    "DepthField",
    "DepthLayout",
    "DepthLoadResult",
    "load_dep_samples",
    "save_dep_samples",
)
