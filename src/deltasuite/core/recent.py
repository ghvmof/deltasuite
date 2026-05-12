"""Persistent list of recently opened projects.

The list lives in ``recent_projects.toml`` next to the user's settings.
Each entry stores the absolute path, a human label and the last-opened
timestamp; missing or unreadable paths are silently skipped on read so
the file can be hand-edited without breaking the app.
"""

from __future__ import annotations

import tomllib
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import tomli_w
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from deltasuite.core.paths import get_app_paths

DEFAULT_LIMIT = 12


class RecentEntry(BaseModel):
    """One recent project record."""

    model_config = ConfigDict(extra="forbid")

    path: Path
    name: str
    opened_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def exists(self) -> bool:
        """``True`` when the on-disk path still exists."""
        return self.path.exists()


class RecentProjects(BaseModel):
    """Container persisted to ``recent_projects.toml``."""

    model_config = ConfigDict(extra="forbid")

    entries: list[RecentEntry] = Field(default_factory=list)
    limit: int = Field(default=DEFAULT_LIMIT, ge=1, le=100)

    def add(self, path: Path, name: str | None = None) -> None:
        """Insert (or move to top) the entry for ``path``."""
        path = Path(path).expanduser().resolve()
        label = name or path.name
        # Remove any existing entry pointing at the same path.
        self.entries = [e for e in self.entries if e.path != path]
        self.entries.insert(0, RecentEntry(path=path, name=label))
        self.entries = self.entries[: self.limit]

    def remove(self, path: Path) -> None:
        """Remove the entry for ``path`` if present."""
        path = Path(path).expanduser().resolve()
        self.entries = [e for e in self.entries if e.path != path]

    def clear(self) -> None:
        """Drop every entry."""
        self.entries.clear()

    def alive(self) -> list[RecentEntry]:
        """Return entries whose target still exists on disk."""
        return [e for e in self.entries if e.exists]


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------


def _to_toml_safe(obj: Any) -> Any:
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _to_toml_safe(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_to_toml_safe(v) for v in obj if v is not None]
    return obj


def _load_from_disk(path: Path) -> RecentProjects:
    if not path.exists():
        return RecentProjects()
    try:
        with path.open("rb") as handle:
            raw: dict[str, Any] = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        logger.warning("Could not read {}: {}", path, exc)
        return RecentProjects()
    try:
        return RecentProjects.model_validate(raw)
    except Exception as exc:
        logger.warning("Invalid recent projects file {}: {}. Resetting.", path, exc)
        return RecentProjects()


def save_recent(recent: RecentProjects, path: Path | None = None) -> Path:
    """Write ``recent`` to ``path`` (or the default location)."""
    target = path or get_app_paths().recent_projects_file
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = _to_toml_safe(recent.model_dump(mode="json"))
    with target.open("wb") as handle:
        tomli_w.dump(payload, handle)
    get_recent.cache_clear()
    return target


@lru_cache(maxsize=1)
def get_recent() -> RecentProjects:
    """Return the cached :class:`RecentProjects` instance."""
    return _load_from_disk(get_app_paths().recent_projects_file)


def push_recent(path: Path, name: str | None = None) -> RecentProjects:
    """Convenience: bump ``path`` to the top of the recent list and persist."""
    recent = get_recent()
    recent.add(path, name=name)
    save_recent(recent)
    return recent


__all__ = (
    "DEFAULT_LIMIT",
    "RecentEntry",
    "RecentProjects",
    "get_recent",
    "push_recent",
    "save_recent",
)
