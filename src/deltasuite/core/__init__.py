"""Core domain logic for DeltaSuite.

This package is intentionally free of any Qt or GUI dependencies, so that
business logic (projects, kernel detection, settings) can be tested and
reused without spinning up a Qt event loop.
"""

from __future__ import annotations

from deltasuite.core.config_files import (
    ConfigDocument,
    ConfigEntry,
    ConfigFormat,
    ConfigSection,
)
from deltasuite.core.kernels import KernelInfo, KernelKind, KernelSet, detect_kernels
from deltasuite.core.logging_setup import configure_logging
from deltasuite.core.paths import AppPaths, get_app_paths
from deltasuite.core.project import Project, ProjectMeta, ProjectType
from deltasuite.core.project_detector import (
    DetectedProject,
    detect_project,
    discover_projects,
)
from deltasuite.core.recent import (
    RecentEntry,
    RecentProjects,
    get_recent,
    push_recent,
    save_recent,
)
from deltasuite.core.results import (
    Field2D,
    Grid2D,
    GridKind,
    ResultDataset,
    ResultFile,
    ResultVariable,
    find_result_files,
)
from deltasuite.core.run_config import RunConfig, RunConfigError, build_run_config
from deltasuite.core.samples import open_bundled_sample
from deltasuite.core.settings import Settings, get_settings, save_settings
from deltasuite.core.timeseries import (
    StationSeries,
    TimeSeriesDataset,
    TimeSeriesFile,
    TimeSeriesVariable,
    find_history_files,
)

__all__ = [
    "AppPaths",
    "ConfigDocument",
    "ConfigEntry",
    "ConfigFormat",
    "ConfigSection",
    "DetectedProject",
    "Field2D",
    "Grid2D",
    "GridKind",
    "KernelInfo",
    "KernelKind",
    "KernelSet",
    "Project",
    "ProjectMeta",
    "ProjectType",
    "RecentEntry",
    "RecentProjects",
    "ResultDataset",
    "ResultFile",
    "ResultVariable",
    "RunConfig",
    "RunConfigError",
    "Settings",
    "StationSeries",
    "TimeSeriesDataset",
    "TimeSeriesFile",
    "TimeSeriesVariable",
    "build_run_config",
    "configure_logging",
    "detect_kernels",
    "detect_project",
    "discover_projects",
    "find_history_files",
    "find_result_files",
    "get_app_paths",
    "get_recent",
    "get_settings",
    "open_bundled_sample",
    "push_recent",
    "save_recent",
    "save_settings",
]
