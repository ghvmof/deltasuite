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
    SmartLoadResult,
    load_smart,
)
from deltasuite.core.dfm_tools_adapter import (
    DfmDatasetResult,
    UVField,
    dfm_tools_version,
    extract_uv_field,
    find_uv_variables,
    is_dfm_tools_available,
    open_curvilinear_smart,
    open_partitioned_smart,
)
from deltasuite.core.hydrolib_adapter import (
    HydrolibLoadResult,
    fmmodel_section_summary,
    fmmodel_set_values,
    hydrolib_version,
    is_hydrolib_available,
    safe_load_fmmodel,
)
from deltasuite.core.kernels import KernelInfo, KernelKind, KernelSet, detect_kernels
from deltasuite.core.logging_setup import configure_logging
from deltasuite.core.mesh_adapter import (
    MeshGeometry,
    MeshLoadResult,
    is_meshkernel_available,
    is_xugrid_available,
    load_mesh_from_dataset,
    load_mesh_from_path,
    meshkernel_version,
    xugrid_version,
)
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
    "DfmDatasetResult",
    "Field2D",
    "Grid2D",
    "GridKind",
    "HydrolibLoadResult",
    "KernelInfo",
    "KernelKind",
    "KernelSet",
    "MeshGeometry",
    "MeshLoadResult",
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
    "SmartLoadResult",
    "StationSeries",
    "TimeSeriesDataset",
    "TimeSeriesFile",
    "TimeSeriesVariable",
    "UVField",
    "build_run_config",
    "configure_logging",
    "detect_kernels",
    "detect_project",
    "dfm_tools_version",
    "discover_projects",
    "extract_uv_field",
    "find_history_files",
    "find_result_files",
    "find_uv_variables",
    "fmmodel_section_summary",
    "fmmodel_set_values",
    "get_app_paths",
    "get_recent",
    "get_settings",
    "hydrolib_version",
    "is_dfm_tools_available",
    "is_hydrolib_available",
    "is_meshkernel_available",
    "is_xugrid_available",
    "load_mesh_from_dataset",
    "load_mesh_from_path",
    "load_smart",
    "meshkernel_version",
    "open_bundled_sample",
    "open_curvilinear_smart",
    "open_partitioned_smart",
    "push_recent",
    "safe_load_fmmodel",
    "save_recent",
    "save_settings",
    "xugrid_version",
]
