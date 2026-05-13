"""Optional integration with Deltares' official ``hydrolib-core`` library.

Why an adapter?
---------------

``hydrolib-core`` (https://github.com/Deltares/HYDROLIB-core) is the official
Python parser/serialiser stack maintained by Deltares for D-Flow FM. We want
DeltaSuite to take advantage of it whenever it's installed because it gives
us:

* Strongly typed Pydantic models for every section of an ``.mdu`` file.
* The exact same validation rules used by the kernel itself.
* Future-proofing against changes in the .mdu schema.

We do **not** want to depend on it strictly though, because:

1. It adds ~60 transitive dependencies (geopandas, dask, numba, lxml, …).
2. It is intentionally strict and will refuse to load real-world ``.mdu``
   files that contain undocumented or legacy keywords (we routinely see
   ``MDUFormatVersion``, ``GuiVersion``, custom user keys etc.).
3. It only handles D-Flow FM ``.mdu`` (not Delft3D-4 ``.mdf``).

This module exposes a tiny, side-effect-free facade: it answers "is hydrolib
available?" and "can you parse this ``.mdu`` for me, returning ``None`` on
failure?" — never raising on anything other than programmer errors. The rest
of DeltaSuite always has our own :mod:`deltasuite.core.config_files` parser
to fall back to.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:  # pragma: no cover -- import only for type checking
    from hydrolib.core.dflowfm.mdu.models import FMModel


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def is_hydrolib_available() -> bool:
    """Return ``True`` if ``hydrolib-core`` can be imported.

    The check is cached, so calling this in tight loops is cheap.
    Importing hydrolib-core itself is a fairly heavy operation (it pulls in
    pydantic-settings, lxml, and ~10 sub-modules), so we only do it once.
    """
    try:
        import hydrolib.core  # noqa: F401

        return True
    except ImportError:
        return False


@lru_cache(maxsize=1)
def hydrolib_version() -> str | None:
    """Return the installed ``hydrolib-core`` version, or ``None`` if absent."""
    if not is_hydrolib_available():
        return None
    try:
        import hydrolib.core as h

        return str(getattr(h, "__version__", "unknown"))
    except Exception:  # pragma: no cover -- defensive
        return None


# ---------------------------------------------------------------------------
# Parse result
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class HydrolibLoadResult:
    """Outcome of an attempt to load an ``.mdu`` with ``hydrolib-core``.

    ``model`` is set when parsing succeeded; ``error`` carries the (sanitised)
    reason otherwise. Exactly one of the two is non-``None``.
    """

    path: Path
    model: FMModel | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.model is not None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def safe_load_fmmodel(path: Path) -> HydrolibLoadResult:
    """Try to parse ``path`` (a ``.mdu``) with ``hydrolib-core``.

    Never raises. If hydrolib-core is unavailable, the file does not exist,
    or the model fails validation, the returned object has ``ok == False``
    and a human-readable ``error`` message that callers can show to the
    user.
    """
    path = Path(path).expanduser()
    if not is_hydrolib_available():
        return HydrolibLoadResult(path=path, error="hydrolib-core is not installed")
    if not path.is_file():
        return HydrolibLoadResult(path=path, error=f"file not found: {path}")
    if path.suffix.lower() != ".mdu":
        return HydrolibLoadResult(
            path=path, error=f"hydrolib-core only handles .mdu files (got {path.suffix})"
        )

    try:
        from hydrolib.core.dflowfm.mdu.models import FMModel

        model = FMModel(filepath=path)
    except Exception as exc:
        msg = _sanitise_error(exc)
        logger.debug("hydrolib-core could not load {}: {}", path, msg)
        return HydrolibLoadResult(path=path, error=msg)
    return HydrolibLoadResult(path=path, model=model)


def fmmodel_section_summary(model: FMModel) -> dict[str, int]:
    """Return ``{section_name: number_of_set_fields}`` for diagnostics."""
    summary: dict[str, int] = {}
    for name, info in type(model).model_fields.items():
        if name in {"filepath", "serializer_config"}:
            continue
        section = getattr(model, name, None)
        if section is None:
            continue
        if hasattr(section, "model_fields"):
            count = sum(
                1
                for fname in type(section).model_fields
                if fname != "comments" and getattr(section, fname, None) is not None
            )
            summary[name] = count
        else:
            # Annotation says it's there but it's not a sub-model (e.g. None).
            _ = info
            summary[name] = 0
    return summary


def fmmodel_set_values(model: FMModel) -> dict[str, dict[str, Any]]:
    """Return a nested ``{section: {field: value}}`` view of all SET fields.

    Fields whose value is ``None`` (i.e. unset, kernel will use default) are
    omitted. This is the canonical view we use to feed editor widgets, do
    cross-validation against our own parser, etc.
    """
    out: dict[str, dict[str, Any]] = {}
    for name in type(model).model_fields:
        if name in {"filepath", "serializer_config"}:
            continue
        section = getattr(model, name, None)
        if section is None or not hasattr(section, "model_fields"):
            continue
        bucket: dict[str, Any] = {}
        for fname in type(section).model_fields:
            if fname == "comments":
                continue
            value = getattr(section, fname, None)
            if value is not None:
                bucket[fname] = value
        if bucket:
            out[name] = bucket
    return out


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _sanitise_error(exc: BaseException) -> str:
    """Turn a hydrolib/pydantic exception into a one-line human message."""
    msg = str(exc).strip().splitlines()[0]
    # pydantic loves to embed monstrous repr() blobs; cut them off so the
    # message remains readable in a status bar.
    if len(msg) > 240:
        msg = msg[:237] + "…"
    return f"{type(exc).__name__}: {msg}"


__all__ = (
    "HydrolibLoadResult",
    "fmmodel_section_summary",
    "fmmodel_set_values",
    "hydrolib_version",
    "is_hydrolib_available",
    "safe_load_fmmodel",
)
