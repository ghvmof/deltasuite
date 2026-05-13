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
from deltasuite.mesh.refine import (
    refine_mesh_based_on_samples,
    refine_mesh_inside_polygon,
)

__all__ = [
    "UGRID_CONVENTIONS",
    "MeshOpResult",
    "delete_node",
    "hanging_edges",
    "make_rectangular_mesh",
    "make_triangular_mesh_from_polygon",
    "merge_nearby_nodes",
    "move_node",
    "orthogonalize_mesh",
    "refine_mesh_based_on_samples",
    "refine_mesh_inside_polygon",
    "round_trip_mesh",
    "save_mesh_to_ugrid_netcdf",
]
