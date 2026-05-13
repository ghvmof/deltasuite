"""Reader / writer for the legacy Delft3D-RGFGRID ``.grd`` format.

Why this exists
---------------
All twelve sample projects under ``examples/delft3d4`` -- and the SWAN
sub-models of every ``examples/dflowfm/*_dwaves`` example -- ship their
mesh as a Deltares-proprietary text file, **not** as UGRID NetCDF. To
let DeltaSuite open and save those projects we therefore need a
self-contained parser and writer for that format.

File layout (RGFGRID 4.x)
-------------------------
The file is plain ASCII, optionally Latin-1::

    *
    * WL | Delft Hydraulics, Delft3D-RGFGRID, Version 4.13.01.02; Sep 2005
    * File creation date: 10:05:37, 26-10-2005
    *
    Coordinate System = Cartesian
    Missing Value = -9.99E+02            (optional)
          M       N
     0 0 0
     ETA=    1   X(1,1) X(2,1) ... X(M,1)
     ETA=    2   X(1,2) X(2,2) ... X(M,2)
     ...
     ETA=    N   X(1,N) X(2,N) ... X(M,N)
     ETA=    1   Y(1,1) Y(2,1) ... Y(M,1)
     ...
     ETA=    N   Y(1,N) Y(2,N) ... Y(M,N)

* Each ``ETA= i`` block lists ``M`` floating-point values (5 per line
  by convention, with continuation lines indented; the parser is
  tolerant to any number of values per line).
* The first ``N`` blocks are the X-coordinates of every node, the
  next ``N`` are the Y-coordinates. There is no explicit
  X-vs-Y separator -- the parser simply consumes ``2 * N`` blocks in
  order.
* ``Missing Value`` (default ``0.0``) marks inactive nodes; we keep
  them in :class:`MeshGeometry` but drop edges that touch them so
  the wireframe stays clean.
"""

from __future__ import annotations

import math
import re
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from loguru import logger

from deltasuite.core.mesh_adapter import MeshGeometry, MeshLoadResult

DEFAULT_MISSING_VALUE = -999.0
"""Documented Delft3D sentinel; only used by the writer when the caller
asks for a non-default missing value. The reader treats nodes as
inactive **only** when the file itself declares ``Missing Value = …``
in its header -- otherwise every node is considered valid."""

_VALUES_PER_LINE = 5
_ETA_RE = re.compile(r"^\s*ETA\s*=\s*(\d+)(.*)$", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Reader
# ---------------------------------------------------------------------------


def load_grd_mesh(path: Path | str) -> MeshLoadResult:
    """Parse a Delft3D RGFGRID ``.grd`` file into a :class:`MeshGeometry`.

    The returned mesh always carries ``structured_shape = (N, M)``,
    so it can be round-tripped back to ``.grd`` later via
    :func:`save_grd_mesh` (or to UGRID NetCDF via
    :func:`save_mesh_to_ugrid_netcdf`).
    """
    file_path = Path(path).expanduser()
    if not file_path.exists():
        return MeshLoadResult(path=file_path, error=f"file not found: {file_path}")
    try:
        text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = file_path.read_text(encoding="latin-1")
    try:
        geom = _parse_grd_text(text)
    except (ValueError, RuntimeError) as exc:
        logger.warning("Could not parse {} as RGFGRID .grd: {}", file_path, exc)
        return MeshLoadResult(path=file_path, error=f"{type(exc).__name__}: {exc}")
    return MeshLoadResult(path=file_path, mesh=geom)


def _parse_grd_text(text: str) -> MeshGeometry:
    lines = text.splitlines()

    n_cols, n_rows, missing, body_start = _parse_header(lines)
    n_total_nodes = n_cols * n_rows

    blocks = _read_eta_blocks(lines[body_start:], expected_count=2 * n_rows, expected_size=n_cols)
    if len(blocks) < 2 * n_rows:
        raise ValueError(
            f"expected {2 * n_rows} ETA blocks, got {len(blocks)} (M={n_cols}, N={n_rows})"
        )

    x_blocks = blocks[:n_rows]
    y_blocks = blocks[n_rows : 2 * n_rows]

    node_x = np.empty(n_total_nodes, dtype=np.float64)
    node_y = np.empty(n_total_nodes, dtype=np.float64)
    for j in range(n_rows):
        node_x[j * n_cols : (j + 1) * n_cols] = x_blocks[j]
        node_y[j * n_cols : (j + 1) * n_cols] = y_blocks[j]

    # A node is inactive only when the file *declares* a Missing Value
    # AND both coordinates match it. A bare ``0 0`` is a perfectly
    # legal node otherwise (lots of real .grd files have nodes at the
    # origin).
    if missing is None:
        valid_mask = np.ones(n_total_nodes, dtype=bool)
    else:
        # A node is inactive only when *both* X and Y equal the
        # sentinel. That matches RGFGRID's own convention -- a node
        # legitimately at (x=missing, y=42.0) is still "real".
        valid_mask = ~(_is_missing(node_x, missing) & _is_missing(node_y, missing))

    edges = _build_structured_edges(n_rows, n_cols, valid_mask)
    faces = _build_structured_faces(n_rows, n_cols, valid_mask)

    return MeshGeometry(
        node_x=node_x,
        node_y=node_y,
        edge_nodes=edges,
        face_nodes=faces,
        structured_shape=(n_rows, n_cols),
    )


def _parse_header(lines: list[str]) -> tuple[int, int, float | None, int]:
    """Return ``(M, N, missing_value_or_None, index_of_first_body_line)``.

    Skips the leading ``*`` comment block, picks up
    ``Coordinate System = …`` and ``Missing Value = …`` if present,
    and reads the ``M N`` dimensions plus the ``0 0 0`` triplet.
    ``missing_value`` is ``None`` when the file does not declare one
    (in which case every node is considered active).
    """
    missing: float | None = None
    n_cols: int | None = None
    n_rows: int | None = None
    triple_seen = False

    for idx, raw in enumerate(lines):
        stripped = raw.strip()
        if not stripped or stripped.startswith("*"):
            continue
        upper = stripped.upper()
        if upper.startswith("COORDINATE SYSTEM"):
            continue  # we keep the raw values; geographic is fine as-is
        if upper.startswith("MISSING VALUE"):
            try:
                missing = float(stripped.split("=", 1)[1])
            except (ValueError, IndexError) as exc:
                raise ValueError(f"could not parse Missing Value line: {stripped!r}") from exc
            continue
        if n_cols is None:
            tokens = stripped.split()
            if len(tokens) < 2:
                raise ValueError(f"expected 'M N' dimensions, got {stripped!r}")
            try:
                n_cols, n_rows = int(tokens[0]), int(tokens[1])
            except ValueError as exc:
                raise ValueError(f"could not parse dimensions: {stripped!r}") from exc
            continue
        if not triple_seen:
            triple_seen = True
            continue
        return n_cols, n_rows or 0, missing, idx

    raise ValueError("RGFGRID header is incomplete (no body found)")


def _read_eta_blocks(
    body_lines: list[str],
    *,
    expected_count: int,
    expected_size: int,
) -> list[list[float]]:
    """Greedy ETA-block reader.

    Walks the body lines once, opening a new block on every
    ``ETA= i`` and accumulating numeric tokens (whether on the same
    line or on continuation lines) until ``expected_size`` values
    have been gathered for that block. Robust to any number of
    values per line.
    """
    blocks: list[list[float]] = []
    current: list[float] | None = None

    for raw in body_lines:
        match = _ETA_RE.match(raw)
        if match:
            if current is not None and len(current) != expected_size:
                raise ValueError(
                    f"unfinished ETA block: expected {expected_size} values, got {len(current)}"
                )
            current = []
            blocks.append(current)
            tail = match.group(2)
            current.extend(_floats_in(tail))
            continue
        if current is None:
            continue  # skip noise before the first ETA= line
        current.extend(_floats_in(raw))
        if len(current) >= expected_size and len(blocks) == expected_count:
            break

    if current is not None and len(current) != expected_size:
        raise ValueError(
            f"unfinished final ETA block: expected {expected_size} values, got {len(current)}"
        )
    return blocks


def _floats_in(text: str) -> list[float]:
    out: list[float] = []
    for token in text.split():
        try:
            out.append(float(token))
        except ValueError:
            continue  # tolerate stray comments / non-numeric noise
    return out


def _is_missing(values: np.ndarray, missing: float) -> np.ndarray:
    if math.isnan(missing):
        return np.asarray(np.isnan(values), dtype=bool)
    return np.asarray(np.isclose(values, missing, atol=1e-12), dtype=bool)


def _build_structured_edges(
    n_rows: int,
    n_cols: int,
    valid_mask: np.ndarray,
) -> np.ndarray:
    """Generate the (n_edges, 2) edge-node connectivity for an M*N grid.

    Vectorised: builds the four-corner index arrays once with
    ``np.arange`` + broadcasting, then masks out edges whose endpoints
    touch an inactive node. Linear in the number of edges, no Python
    loops over individual cells.
    """
    if n_rows < 1 or n_cols < 1:
        return np.empty((0, 2), dtype=np.int64)

    grid = np.arange(n_rows * n_cols, dtype=np.int64).reshape(n_rows, n_cols)
    mask_grid = valid_mask.reshape(n_rows, n_cols)

    edges_list: list[np.ndarray] = []

    if n_cols > 1:
        a = grid[:, :-1].ravel()
        b = grid[:, 1:].ravel()
        keep = (mask_grid[:, :-1] & mask_grid[:, 1:]).ravel()
        if keep.any():
            edges_list.append(np.column_stack([a[keep], b[keep]]))
    if n_rows > 1:
        a = grid[:-1, :].ravel()
        b = grid[1:, :].ravel()
        keep = (mask_grid[:-1, :] & mask_grid[1:, :]).ravel()
        if keep.any():
            edges_list.append(np.column_stack([a[keep], b[keep]]))

    if not edges_list:
        return np.empty((0, 2), dtype=np.int64)
    return np.concatenate(edges_list, axis=0)


def _build_structured_faces(
    n_rows: int,
    n_cols: int,
    valid_mask: np.ndarray,
) -> np.ndarray | None:
    """Return the (n_faces, 4) quad face connectivity, vectorised."""
    if n_rows < 2 or n_cols < 2:
        return None

    grid = np.arange(n_rows * n_cols, dtype=np.int64).reshape(n_rows, n_cols)
    mask_grid = valid_mask.reshape(n_rows, n_cols)

    a = grid[:-1, :-1]
    b = grid[:-1, 1:]
    c = grid[1:, 1:]
    d = grid[1:, :-1]
    keep = mask_grid[:-1, :-1] & mask_grid[:-1, 1:] & mask_grid[1:, 1:] & mask_grid[1:, :-1]
    if not keep.any():
        return None
    keep_flat = keep.ravel()
    quads = np.column_stack([a.ravel(), b.ravel(), c.ravel(), d.ravel()])
    return np.asarray(quads[keep_flat], dtype=np.int64)


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------


def save_grd_mesh(
    mesh: MeshGeometry,
    path: Path | str,
    *,
    coordinate_system: str = "Cartesian",
    missing_value: float | None = None,
    overwrite: bool = True,
) -> MeshLoadResult:
    """Serialise ``mesh`` to a Delft3D-RGFGRID ``.grd`` file.

    Only meshes with a known ``structured_shape`` (``(N, M)``) can be
    written -- triangulated or locally-refined meshes have no
    well-defined column ordering and would lose information. In that
    case the function returns a structured error rather than guessing.
    """
    target = Path(path).expanduser()
    if target.exists() and not overwrite:
        return MeshLoadResult(path=target, error=f"target already exists: {target}")
    if mesh.structured_shape is None:
        return MeshLoadResult(
            path=target,
            error=(
                "mesh has no structured_shape: only meshes generated as "
                "rectangular grids (or loaded from .grd) can be saved as .grd. "
                "Use save_mesh_to_ugrid_netcdf() instead."
            ),
        )
    n_rows, n_cols = mesh.structured_shape
    expected = n_rows * n_cols
    if mesh.n_nodes != expected:
        return MeshLoadResult(
            path=target,
            error=(
                f"node count {mesh.n_nodes} does not match structured_shape "
                f"{mesh.structured_shape} (= {expected})"
            ),
        )

    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        text = _format_grd_text(mesh, coordinate_system, missing_value)
        target.write_text(text, encoding="utf-8")
    except (OSError, ValueError) as exc:  # pragma: no cover -- defensive
        logger.warning("RGFGRID .grd write failed: {}", exc)
        return MeshLoadResult(path=target, error=f"{type(exc).__name__}: {exc}")
    return MeshLoadResult(path=target, mesh=mesh)


def _format_grd_text(mesh: MeshGeometry, coord_sys: str, missing: float | None) -> str:
    assert mesh.structured_shape is not None
    n_rows, n_cols = mesh.structured_shape
    node_x = np.asarray(mesh.node_x, dtype=np.float64).reshape(n_rows, n_cols)
    node_y = np.asarray(mesh.node_y, dtype=np.float64).reshape(n_rows, n_cols)

    now = datetime.now(UTC).strftime("%H:%M:%S, %d-%m-%Y")
    header = [
        "*",
        "* DeltaSuite, RGFGRID-compatible writer",
        f"* File creation date: {now}",
        "*",
        f"Coordinate System = {coord_sys}",
    ]
    if missing is not None:
        header.append(f"Missing Value = {_fmt_value(missing)}")
    header.append(f"{n_cols:8d}{n_rows:8d}")
    header.append(" 0 0 0")

    body: list[str] = []
    body.extend(_format_eta_blocks(node_x))
    body.extend(_format_eta_blocks(node_y))

    return "\n".join(header + body) + "\n"


def _format_eta_blocks(values: np.ndarray) -> list[str]:
    """Emit ``N`` ETA blocks with up to 5 values per line."""
    n_rows, n_cols = values.shape
    lines: list[str] = []
    for j in range(n_rows):
        row = values[j]
        prefix_first = f" ETA= {j + 1:4d} "
        # First line: prefix + up to (5 - 0) values, padded to the
        # same column the rest of the lines start at.
        first_chunk = row[:_VALUES_PER_LINE]
        first = prefix_first + "  ".join(_fmt_value(v) for v in first_chunk)
        lines.append(first)
        # Continuation lines: indented to align values
        offset = _VALUES_PER_LINE
        while offset < n_cols:
            chunk = row[offset : offset + _VALUES_PER_LINE]
            line = " " * 13 + "  ".join(_fmt_value(v) for v in chunk)
            lines.append(line)
            offset += _VALUES_PER_LINE
    return lines


def _fmt_value(value: float) -> str:
    """RGFGRID-style scientific notation, ``1.23000000000000000E+02``."""
    return f"{value: .17E}"


__all__ = (
    "DEFAULT_MISSING_VALUE",
    "load_grd_mesh",
    "save_grd_mesh",
)
