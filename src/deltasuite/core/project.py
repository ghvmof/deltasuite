"""DeltaSuite project model.

A *project* groups together all input and output files of a Delft3D study,
plus user metadata (name, description, author, last modified date) and
the simulation kind (Delft3D 4 ``.mdf``-based or D-Flow FM ``.mdu``-based).

Projects are stored as a directory containing:

* ``deltasuite.toml`` — project metadata
* The actual model input files (``.mdf``, ``.mdu``, ``.grd``, ``.dep``, ...)
* ``output/`` — produced by simulation runs
"""

from __future__ import annotations

import tomllib
from datetime import datetime
from enum import StrEnum, unique
from pathlib import Path
from typing import Any
from uuid import uuid4

import tomli_w
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

PROJECT_FILE_NAME: str = "deltasuite.toml"
PROJECT_FORMAT_VERSION: int = 1


def _drop_none(obj: Any) -> Any:
    """Recursively strip ``None`` values from ``obj`` so it can be TOML-encoded."""
    if isinstance(obj, dict):
        return {k: _drop_none(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_drop_none(v) for v in obj if v is not None]
    return obj


@unique
class ProjectType(StrEnum):
    """Supported simulation engine families."""

    DELFT3D4 = "delft3d4"
    """Classic Delft3D 4 with structured grids (.mdf)."""

    DFLOWFM = "dflowfm"
    """D-Flow Flexible Mesh with unstructured grids (.mdu)."""

    DIMR = "dimr"
    """Multi-engine DIMR coupling (config_dimr.xml)."""

    UNKNOWN = "unknown"


class ProjectMeta(BaseModel):
    """Metadata stored in ``deltasuite.toml``.

    The file format version is included so that DeltaSuite can detect old
    projects and migrate them when the format evolves.
    """

    model_config = ConfigDict(extra="forbid")

    format_version: int = Field(default=PROJECT_FORMAT_VERSION, ge=1)
    uuid: str = Field(default_factory=lambda: str(uuid4()))
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    author: str = ""
    project_type: ProjectType = ProjectType.UNKNOWN
    main_input_file: str | None = None
    """Relative path inside the project to the entry-point file (.mdf, .mdu, ...)."""
    created_at: datetime = Field(default_factory=lambda: datetime.now().astimezone())
    modified_at: datetime = Field(default_factory=lambda: datetime.now().astimezone())
    tags: list[str] = Field(default_factory=list)


class Project:
    """A DeltaSuite project rooted in a directory on disk."""

    def __init__(self, root: Path, meta: ProjectMeta) -> None:
        self._root = Path(root).expanduser().resolve()
        self._meta = meta

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------
    @property
    def root(self) -> Path:
        """Absolute path to the project directory."""
        return self._root

    @property
    def meta(self) -> ProjectMeta:
        """Project metadata."""
        return self._meta

    @property
    def project_file(self) -> Path:
        """Absolute path to the ``deltasuite.toml`` file."""
        return self._root / PROJECT_FILE_NAME

    @property
    def output_dir(self) -> Path:
        """Directory where simulation outputs are written."""
        return self._root / "output"

    @property
    def main_input_path(self) -> Path | None:
        """Absolute path to the main input file (e.g. ``f34.mdf``)."""
        if not self._meta.main_input_file:
            return None
        return self._root / self._meta.main_input_file

    # ------------------------------------------------------------------
    # Constructors
    # ------------------------------------------------------------------
    @classmethod
    def create(
        cls,
        root: Path,
        name: str,
        *,
        project_type: ProjectType = ProjectType.UNKNOWN,
        description: str = "",
        author: str = "",
        main_input_file: str | None = None,
    ) -> Project:
        """Create a brand new project on disk and return it."""
        root = Path(root).expanduser().resolve()
        if root.exists() and any(root.iterdir()):
            raise FileExistsError(f"Project directory is not empty: {root}")
        root.mkdir(parents=True, exist_ok=True)

        meta = ProjectMeta(
            name=name,
            description=description,
            author=author,
            project_type=project_type,
            main_input_file=main_input_file,
        )
        project = cls(root, meta)
        project.output_dir.mkdir(exist_ok=True)
        project.save()
        logger.info("Created new project '{}' at {}", name, root)
        return project

    @classmethod
    def open(cls, path: Path) -> Project:
        """Open a project from either its directory or its ``deltasuite.toml`` file."""
        path = Path(path).expanduser().resolve()
        if path.is_dir():
            project_file = path / PROJECT_FILE_NAME
            root = path
        else:
            project_file = path
            root = path.parent

        if not project_file.is_file():
            raise FileNotFoundError(f"No project file at {project_file}")

        with project_file.open("rb") as handle:
            raw: dict[str, Any] = tomllib.load(handle)
        meta = ProjectMeta.model_validate(raw)
        logger.debug("Opened project '{}' from {}", meta.name, root)
        return cls(root, meta)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def save(self) -> None:
        """Write the project metadata to ``deltasuite.toml``."""
        self._meta = self._meta.model_copy(update={"modified_at": datetime.now().astimezone()})
        payload: dict[str, Any] = _drop_none(self._meta.model_dump(mode="json"))
        with self.project_file.open("wb") as handle:
            tomli_w.dump(payload, handle)
        logger.debug("Saved project '{}' to {}", self._meta.name, self.project_file)

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------
    def list_input_files(self) -> list[Path]:
        """List all model input files recognised in the project root."""
        suffixes = {
            ".mdf",
            ".mdu",
            ".grd",
            ".dep",
            ".bnd",
            ".bca",
            ".bch",
            ".bct",
            ".dis",
            ".obs",
            ".crs",
            ".enc",
            ".ldb",
            ".par",
            ".thd",
            ".wnd",
            ".src",
            ".xyz",
            ".pli",
            ".pliz",
            ".xml",
        }
        return sorted(p for p in self._root.iterdir() if p.suffix.lower() in suffixes)

    def __repr__(self) -> str:
        return (
            f"Project(name={self._meta.name!r}, type={self._meta.project_type.value}, "
            f"root={self._root})"
        )
