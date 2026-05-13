"""Tests for the optional ``dfm-tools`` integration."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from deltasuite.core import (
    DfmDatasetResult,
    UVField,
    dfm_tools_version,
    extract_uv_field,
    find_uv_variables,
    is_dfm_tools_available,
    open_curvilinear_smart,
    open_partitioned_smart,
)

# ---------------------------------------------------------------------------
# Synthetic dataset fixtures
# ---------------------------------------------------------------------------


def _curvilinear_uv_dataset() -> xr.Dataset:
    """Build a small Delft3D-4-style ``trim`` dataset with U1/V1."""
    m, n, t = 6, 8, 3
    xc = np.linspace(0.0, 100.0, m)[:, None] * np.ones(n)[None, :]
    yc = np.linspace(0.0, 80.0, n)[None, :] * np.ones(m)[:, None]
    u = np.random.default_rng(seed=0).standard_normal((t, m, n)).astype("f4")
    v = np.random.default_rng(seed=1).standard_normal((t, m, n)).astype("f4")
    return xr.Dataset(
        data_vars={
            "U1": (("time", "M", "N"), u, {"units": "m s-1"}),
            "V1": (("time", "M", "N"), v, {"units": "m s-1"}),
        },
        coords={
            "XCOR": (("M", "N"), xc),
            "YCOR": (("M", "N"), yc),
            "XZ": (("M", "N"), xc),
            "YZ": (("M", "N"), yc),
            "time": np.arange(t),
        },
    )


def _ugrid_uv_dataset() -> xr.Dataset:
    """Build a tiny D-Flow-FM-style dataset with mesh2d_ucx / mesh2d_ucy."""
    n_face, t = 12, 2
    fx = np.linspace(0.0, 100.0, n_face)
    fy = np.linspace(0.0, 50.0, n_face)
    rng = np.random.default_rng(seed=42)
    return xr.Dataset(
        data_vars={
            "mesh2d_ucx": (
                ("time", "nFaces"),
                rng.standard_normal((t, n_face)).astype("f4"),
                {"units": "m/s"},
            ),
            "mesh2d_ucy": (
                ("time", "nFaces"),
                rng.standard_normal((t, n_face)).astype("f4"),
                {"units": "m/s"},
            ),
        },
        coords={
            "mesh2d_face_x": ("nFaces", fx),
            "mesh2d_face_y": ("nFaces", fy),
            "time": np.arange(t),
        },
    )


# ---------------------------------------------------------------------------
# Always-on tests (no dfm-tools required)
# ---------------------------------------------------------------------------


def test_is_dfm_tools_available_returns_bool() -> None:
    assert isinstance(is_dfm_tools_available(), bool)


def test_dfm_tools_version_matches_availability() -> None:
    if is_dfm_tools_available():
        v = dfm_tools_version()
        assert isinstance(v, str)
        assert v
    else:
        assert dfm_tools_version() is None


def test_open_partitioned_smart_missing_file(tmp_path: Path) -> None:
    res = open_partitioned_smart(tmp_path / "no_such.nc")
    assert isinstance(res, DfmDatasetResult)
    assert not res.ok
    assert res.error is not None


def test_open_curvilinear_smart_missing_file(tmp_path: Path) -> None:
    res = open_curvilinear_smart(tmp_path / "no_such.nc")
    assert not res.ok
    assert res.error is not None


def test_find_uv_variables_curvilinear() -> None:
    ds = _curvilinear_uv_dataset()
    u, v = find_uv_variables(ds)
    assert u == "U1"
    assert v == "V1"


def test_find_uv_variables_ugrid() -> None:
    ds = _ugrid_uv_dataset()
    u, v = find_uv_variables(ds)
    assert u == "mesh2d_ucx"
    assert v == "mesh2d_ucy"


def test_find_uv_variables_none_when_missing() -> None:
    ds = xr.Dataset({"foo": (("x",), np.zeros(3))})
    u, v = find_uv_variables(ds)
    assert u is None
    assert v is None


# ---------------------------------------------------------------------------
# UV extraction (does not require dfm-tools, only numpy/xarray)
# ---------------------------------------------------------------------------


def test_extract_uv_field_curvilinear() -> None:
    ds = _curvilinear_uv_dataset()
    field = extract_uv_field(ds, time_index=1, stride=1)
    assert isinstance(field, UVField)
    assert field.units == "m s-1"
    assert field.u.shape == (6, 8)
    assert field.v.shape == (6, 8)
    assert field.x.shape == (6, 8)
    assert field.y.shape == (6, 8)
    # No NaNs in the synthetic data, so mask should be all False.
    assert not field.mask.any()
    # Magnitude is non-negative.
    assert (field.magnitude >= 0).all()


def test_extract_uv_field_curvilinear_with_stride() -> None:
    ds = _curvilinear_uv_dataset()
    field = extract_uv_field(ds, time_index=0, stride=2)
    assert field is not None
    # stride=2 over 6x8 -> 3x4
    assert field.u.shape == (3, 4)
    assert field.x.shape == (3, 4)


def test_extract_uv_field_ugrid() -> None:
    ds = _ugrid_uv_dataset()
    field = extract_uv_field(ds, time_index=0, stride=1)
    assert field is not None
    assert field.units == "m/s"
    assert field.u.shape == (12,)
    assert field.x.shape == (12,)


def test_extract_uv_field_returns_none_when_no_uv() -> None:
    ds = xr.Dataset({"sealevel": (("t",), np.zeros(3))})
    assert extract_uv_field(ds) is None


def test_extract_uv_field_clamps_time_index() -> None:
    ds = _curvilinear_uv_dataset()  # t=3
    field = extract_uv_field(ds, time_index=99)
    assert field is not None  # silently clamped to the last time step


def test_uvfield_magnitude_is_correct() -> None:
    field = UVField(
        x=np.array([0.0, 1.0]),
        y=np.array([0.0, 1.0]),
        u=np.array([3.0, 0.0]),
        v=np.array([4.0, 0.0]),
        mask=np.array([False, False]),
        units="m/s",
    )
    np.testing.assert_allclose(field.magnitude, [5.0, 0.0])


# ---------------------------------------------------------------------------
# Tests that actually require dfm-tools (skipped silently otherwise)
# ---------------------------------------------------------------------------


pytestmark_dfm = pytest.mark.skipif(
    not is_dfm_tools_available(),
    reason="dfm-tools is not installed",
)


@pytestmark_dfm
def test_dfm_tools_version_string_format() -> None:
    """The reported version should look like a semver."""
    v = dfm_tools_version()
    assert v is not None
    parts = v.split(".")
    assert len(parts) >= 2
    assert parts[0].isdigit()
