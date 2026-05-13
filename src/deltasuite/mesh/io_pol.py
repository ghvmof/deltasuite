"""Reader for the legacy Delft3D / D-Flow FM polygon formats.

Why this exists
---------------
``meshkernel`` triangulators and the GUI's "Triangulate from polygon"
action both need a closed 2-D ring as input. The standard way to ship
such a ring with a Delft3D project is one of three plain-text formats:

* ``.pol`` - "polygon file", typically used for thin dams, dry points
  or domain extents (e.g. ``examples/delft3d4/07_wave/obw.pol``).
* ``.ldb`` - "land boundary", a polyline that traces a coastline
  (e.g. ``examples/delft3d4/01_standard/f34.ldb``).
* ``.xy``  - bare ``X Y`` pairs without any header.

All three share the same body grammar -- one ``X Y`` per line, with
optional trailing columns -- so a single tolerant parser handles them
together. ``.pol`` and ``.ldb`` may contain *several* polygons stacked
in the same file, each preceded by a name string and a ``nrows ncols``
header; the parser returns them all in order so the caller can pick
(usually the largest one is taken as the domain ring).

Lines starting with ``*`` or ``#`` and blank lines are ignored
everywhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from loguru import logger


@dataclass(frozen=True, slots=True)
class Polygon2D:
    """One closed (or open) 2-D ring extracted from a ``.pol`` / ``.ldb``."""

    name: str
    x: np.ndarray  # shape (n_vertices,), float64
    y: np.ndarray  # shape (n_vertices,), float64

    @property
    def n_vertices(self) -> int:
        return int(self.x.size)

    @property
    def is_closed(self) -> bool:
        if self.x.size < 2:
            return False
        return bool(self.x[0] == self.x[-1] and self.y[0] == self.y[-1])

    def closed(self) -> Polygon2D:
        """Return a copy with the first vertex appended at the end."""
        if self.is_closed:
            return self
        return Polygon2D(
            name=self.name,
            x=np.append(self.x, self.x[0]),
            y=np.append(self.y, self.y[0]),
        )


@dataclass(frozen=True, slots=True)
class PolygonLoadResult:
    """Wrapper returned by :func:`load_polygon_file`."""

    path: Path
    polygons: tuple[Polygon2D, ...] = ()
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and len(self.polygons) > 0

    def largest(self) -> Polygon2D | None:
        """Return the polygon with the most vertices, or ``None`` if empty."""
        if not self.polygons:
            return None
        return max(self.polygons, key=lambda p: p.n_vertices)


# ---------------------------------------------------------------------------
# Reader
# ---------------------------------------------------------------------------


def load_polygon_file(path: Path | str) -> PolygonLoadResult:
    """Parse a Delft3D ``.pol`` / ``.ldb`` / ``.xy`` polygon file.

    The function is tolerant by design: any line that isn't recognised
    as a comment or as a row of floats is treated as a header (either a
    polygon name or a ``nrows ncols`` declaration) and starts a new
    polygon. Headers are not validated -- the actual point count comes
    from the body. This keeps the parser robust against the small
    syntactic variations seen in the wild.
    """
    file_path = Path(path).expanduser()
    if not file_path.exists():
        return PolygonLoadResult(path=file_path, error=f"file not found: {file_path}")
    try:
        text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = file_path.read_text(encoding="latin-1")

    try:
        polygons = _parse_polygon_text(text, default_name=file_path.stem)
    except ValueError as exc:
        logger.warning("Could not parse {} as polygon file: {}", file_path, exc)
        return PolygonLoadResult(path=file_path, error=f"ValueError: {exc}")

    if not polygons:
        return PolygonLoadResult(
            path=file_path,
            error="file contained no polygons (no rows of floats found)",
        )
    return PolygonLoadResult(path=file_path, polygons=tuple(polygons))


def _parse_polygon_text(text: str, *, default_name: str) -> list[Polygon2D]:
    polygons: list[Polygon2D] = []
    current_name = default_name
    current_x: list[float] = []
    current_y: list[float] = []
    seen_header = False

    def flush() -> None:
        nonlocal current_x, current_y
        if current_x:
            polygons.append(
                Polygon2D(
                    name=current_name,
                    x=np.asarray(current_x, dtype=np.float64),
                    y=np.asarray(current_y, dtype=np.float64),
                )
            )
        current_x = []
        current_y = []

    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith(("*", "#")):
            continue
        tokens = stripped.split()
        # A row of floats with at least 2 values is a vertex.
        try:
            x_val = float(tokens[0])
            y_val = float(tokens[1])
        except (ValueError, IndexError):
            # Treat as a header: flush the previous polygon (if any) and
            # use the first token as the name. We do not need the
            # subsequent ``nrows ncols`` row -- it is consumed silently
            # because it parses as floats too, but its values are
            # tiny integers that downstream code will simply add as
            # extra "vertices" -- so we instead set a flag to skip
            # the very next line if it looks like an integer pair.
            flush()
            current_name = stripped if stripped else default_name
            seen_header = True
            continue

        # Heuristic: when a header was just seen, the next line that
        # parses as two integers is the ``nrows ncols`` row -- skip it.
        if (
            seen_header
            and len(tokens) == 2
            and float(tokens[0]).is_integer()
            and float(tokens[1]).is_integer()
            and 0 < x_val < 1e6
            and 0 < y_val < 1e6
            and x_val == int(x_val)
            and y_val == int(y_val)
        ):
            seen_header = False
            continue

        seen_header = False
        current_x.append(x_val)
        current_y.append(y_val)

    flush()
    return polygons


__all__ = (
    "Polygon2D",
    "PolygonLoadResult",
    "load_polygon_file",
)
