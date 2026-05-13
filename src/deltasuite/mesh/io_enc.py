"""Reader / writer for the legacy Delft3D ``.enc`` enclosure format.

The ``.enc`` (enclosure) file accompanies a ``.grd`` mesh and lists
the ``(m, n)`` integer indices of the polygon vertices that bound
the *active* portion of the curvilinear grid. Each vertex addresses
a node of the underlying grid, *not* a real-world coordinate, so the
file is independent of the coordinate system.

File layout
-----------
::

         1     1   *** begin external enclosure
        67     1
        67    76
         1    76
         1     1   *** end external grid enclosure

* The first and last vertex must coincide -- the polygon is closed.
* Comments after the indices (``***``-prefixed or anything
  non-numeric) are ignored.
* Multiple polygons can in principle be stacked in a single file,
  but the standard usage is a single closed polygon. Our writer
  emits one polygon at a time; the reader returns whichever vertices
  it finds.

The functions below convert between the on-disk integer-index
representation and a Python-friendly :class:`Enclosure` object that
also exposes the corresponding real-world ``(x, y)`` coordinates
when paired with the enclosure's parent :class:`MeshGeometry`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from loguru import logger

from deltasuite.core.mesh_adapter import MeshGeometry


@dataclass(frozen=True, slots=True)
class Enclosure:
    """Closed polygon in ``(m, n)`` index space, plus optional XY."""

    m_indices: np.ndarray  # 1-based, shape (n_vertices,)
    n_indices: np.ndarray  # 1-based, shape (n_vertices,)
    x: np.ndarray | None = None  # real-world coordinates (optional)
    y: np.ndarray | None = None

    @property
    def n_vertices(self) -> int:
        return int(self.m_indices.size)


@dataclass(frozen=True, slots=True)
class EnclosureLoadResult:
    """Wrapper returned by :func:`load_enc`."""

    path: Path
    enclosure: Enclosure | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.enclosure is not None


# ---------------------------------------------------------------------------
# Reader
# ---------------------------------------------------------------------------


def load_enc(
    path: Path | str,
    mesh: MeshGeometry | None = None,
) -> EnclosureLoadResult:
    """Parse a Delft3D ``.enc`` enclosure file.

    If ``mesh`` is supplied **and** carries ``structured_shape``, the
    returned :class:`Enclosure` is enriched with the corresponding
    ``(x, y)`` coordinates so the polygon can be drawn directly on
    top of the mesh in the GUI.
    """
    file_path = Path(path).expanduser()
    if not file_path.exists():
        return EnclosureLoadResult(path=file_path, error=f"file not found: {file_path}")
    try:
        text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = file_path.read_text(encoding="latin-1")

    try:
        m_idx, n_idx = _parse_enc_text(text)
    except ValueError as exc:
        logger.warning("Could not parse {} as .enc: {}", file_path, exc)
        return EnclosureLoadResult(path=file_path, error=f"ValueError: {exc}")

    enclosure = Enclosure(m_indices=m_idx, n_indices=n_idx)
    if mesh is not None and mesh.structured_shape is not None:
        try:
            enclosure = _attach_xy(enclosure, mesh)
        except IndexError as exc:
            return EnclosureLoadResult(
                path=file_path,
                error=f"enclosure references nodes outside mesh: {exc}",
            )
    return EnclosureLoadResult(path=file_path, enclosure=enclosure)


def _parse_enc_text(text: str) -> tuple[np.ndarray, np.ndarray]:
    m_values: list[int] = []
    n_values: list[int] = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("*"):
            continue
        # Stop reading at the first non-numeric token after the indices
        tokens = stripped.split()
        if len(tokens) < 2:
            continue
        try:
            m, n = int(tokens[0]), int(tokens[1])
        except ValueError:
            continue
        m_values.append(m)
        n_values.append(n)
    if len(m_values) < 3:
        raise ValueError(f"need at least 3 vertices, got {len(m_values)}")
    if (m_values[0], n_values[0]) != (m_values[-1], n_values[-1]):
        # Auto-close so callers can rely on it
        m_values.append(m_values[0])
        n_values.append(n_values[0])
    return (
        np.asarray(m_values, dtype=np.int64),
        np.asarray(n_values, dtype=np.int64),
    )


def _attach_xy(enclosure: Enclosure, mesh: MeshGeometry) -> Enclosure:
    assert mesh.structured_shape is not None
    n_rows, n_cols = mesh.structured_shape
    nx = np.asarray(mesh.node_x, dtype=np.float64).reshape(n_rows, n_cols)
    ny = np.asarray(mesh.node_y, dtype=np.float64).reshape(n_rows, n_cols)

    # The .enc file uses 1-based indices, with M = column index (so it
    # ranges over n_cols) and N = row index (over n_rows).
    m_zero = enclosure.m_indices - 1
    n_zero = enclosure.n_indices - 1
    if m_zero.min() < 0 or m_zero.max() >= n_cols or n_zero.min() < 0 or n_zero.max() >= n_rows:
        raise IndexError(f"vertex out of range: m in [1, {n_cols}], n in [1, {n_rows}]")
    x = nx[n_zero, m_zero]
    y = ny[n_zero, m_zero]
    return Enclosure(
        m_indices=enclosure.m_indices,
        n_indices=enclosure.n_indices,
        x=x,
        y=y,
    )


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------


def save_enc(
    path: Path | str,
    m_indices: np.ndarray | list[int],
    n_indices: np.ndarray | list[int],
    *,
    overwrite: bool = True,
) -> EnclosureLoadResult:
    """Write an enclosure polygon to ``path`` in Delft3D ``.enc`` format.

    The polygon is auto-closed (first vertex appended at the end if
    missing). The file is human-readable, formatted as right-aligned
    8-column integers like the Deltares originals.
    """
    target = Path(path).expanduser()
    if target.exists() and not overwrite:
        return EnclosureLoadResult(path=target, error=f"target already exists: {target}")
    m = np.asarray(m_indices, dtype=np.int64).ravel()
    n = np.asarray(n_indices, dtype=np.int64).ravel()
    if m.size != n.size:
        return EnclosureLoadResult(
            path=target,
            error=f"m_indices and n_indices differ in size ({m.size} vs {n.size})",
        )
    if m.size < 3:
        return EnclosureLoadResult(
            path=target,
            error=f"need at least 3 vertices, got {m.size}",
        )
    if (m[0], n[0]) != (m[-1], n[-1]):
        m = np.append(m, m[0])
        n = np.append(n, n[0])

    target.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"  {m[0]:5d}  {n[0]:5d}   *** begin external enclosure"]
    for k in range(1, m.size - 1):
        lines.append(f"  {m[k]:5d}  {n[k]:5d}")
    lines.append(f"  {m[-1]:5d}  {n[-1]:5d}   *** end external grid enclosure")
    try:
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError as exc:  # pragma: no cover -- defensive
        return EnclosureLoadResult(path=target, error=f"OSError: {exc}")

    return EnclosureLoadResult(
        path=target,
        enclosure=Enclosure(m_indices=m, n_indices=n),
    )


__all__ = (
    "Enclosure",
    "EnclosureLoadResult",
    "load_enc",
    "save_enc",
)
