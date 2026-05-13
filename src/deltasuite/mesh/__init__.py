"""2-D mesh generation, refinement, editing and persistence.

All functions here are **library-agnostic** at the boundary: they take
and return :class:`~deltasuite.core.mesh_adapter.MeshGeometry` /
:class:`MeshOpResult`, and surface failures (including ``meshkernel``
not being installed) as a structured error rather than an exception.
That makes them safe to call straight from Qt slots without ``try`` /
``except`` ceremony.
"""

from __future__ import annotations

from deltasuite.mesh.edit import (
    delete_node,
    hanging_edges,
    merge_nearby_nodes,
    move_node,
    orthogonalize_mesh,
)
from deltasuite.mesh.generate import (
    MeshOpResult,
    make_rectangular_mesh,
    make_triangular_mesh_from_polygon,
)
from deltasuite.mesh.io import (
    UGRID_CONVENTIONS,
    round_trip_mesh,
    save_mesh_to_ugrid_netcdf,
)
from deltasuite.mesh.io_dep import (
    DEFAULT_MISSING_VALUE as DEPTH_DEFAULT_MISSING_VALUE,
)
from deltasuite.mesh.io_dep import (
    DepthField,
    DepthLayout,
    DepthLoadResult,
    load_dep_samples,
    save_dep_samples,
)
from deltasuite.mesh.io_enc import (
    Enclosure,
    EnclosureLoadResult,
    load_enc,
    save_enc,
)
from deltasuite.mesh.io_grd import (
    DEFAULT_MISSING_VALUE,
    load_grd_mesh,
    save_grd_mesh,
)
from deltasuite.mesh.io_pol import (
    Polygon2D,
    PolygonLoadResult,
    load_polygon_file,
)
from deltasuite.mesh.refine import (
    refine_mesh_based_on_samples,
    refine_mesh_inside_polygon,
)

__all__ = [
    "DEFAULT_MISSING_VALUE",
    "DEPTH_DEFAULT_MISSING_VALUE",
    "UGRID_CONVENTIONS",
    "DepthField",
    "DepthLayout",
    "DepthLoadResult",
    "Enclosure",
    "EnclosureLoadResult",
    "MeshOpResult",
    "Polygon2D",
    "PolygonLoadResult",
    "delete_node",
    "hanging_edges",
    "load_dep_samples",
    "load_enc",
    "load_grd_mesh",
    "load_polygon_file",
    "make_rectangular_mesh",
    "make_triangular_mesh_from_polygon",
    "merge_nearby_nodes",
    "move_node",
    "orthogonalize_mesh",
    "refine_mesh_based_on_samples",
    "refine_mesh_inside_polygon",
    "round_trip_mesh",
    "save_dep_samples",
    "save_enc",
    "save_grd_mesh",
    "save_mesh_to_ugrid_netcdf",
]
