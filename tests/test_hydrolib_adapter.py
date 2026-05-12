"""Tests for the optional ``hydrolib-core`` integration.

These tests run unconditionally on CI: if ``hydrolib-core`` is not installed
they exercise the "graceful degradation" code path (``ok=False`` /
``hydrolib_validated=False``); when it *is* installed (``[delft3d]`` extra)
they additionally check the cross-validation path against a real .mdu.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from deltasuite.core import (
    HydrolibLoadResult,
    SmartLoadResult,
    fmmodel_section_summary,
    fmmodel_set_values,
    hydrolib_version,
    is_hydrolib_available,
    load_smart,
    safe_load_fmmodel,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


_CLEAN_MDU = """\
[General]
Program           = D-Flow FM
Version           = 1.2.105

[geometry]
NetFile           = mesh.nc
BedlevType        = 3

[time]
RefDate           = 20240101
TStart            = 0
TStop             = 1440
"""


_LEGACY_MDU = """\
[General]
Program           = D-Flow FM
Version           = 1.2.105
MDUFormatVersion  = 1.09
GuiVersion        = 1.6.6.40483

[geometry]
NetFile           = mesh.nc
BedlevType        = 3

[time]
RefDate           = 20240101
TStart            = 0
TStop             = 1440
"""


_MDF = """\
Runtxt   = #demo run#
MNKmax   = 30 30 5
Tunit    = #M#
Tstart   = 0.0
Tstop    = 1440.0
"""


@pytest.fixture()
def clean_mdu(tmp_path: Path) -> Path:
    p = tmp_path / "clean.mdu"
    p.write_text(_CLEAN_MDU, encoding="utf-8")
    return p


@pytest.fixture()
def legacy_mdu(tmp_path: Path) -> Path:
    p = tmp_path / "legacy.mdu"
    p.write_text(_LEGACY_MDU, encoding="utf-8")
    return p


@pytest.fixture()
def sample_mdf(tmp_path: Path) -> Path:
    p = tmp_path / "demo.mdf"
    p.write_text(_MDF, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Always-on tests
# ---------------------------------------------------------------------------


def test_is_hydrolib_available_returns_bool() -> None:
    """Detection helper must never raise and must return a real bool."""
    assert isinstance(is_hydrolib_available(), bool)


def test_hydrolib_version_matches_availability() -> None:
    """Version string must be present iff library is importable."""
    if is_hydrolib_available():
        v = hydrolib_version()
        assert isinstance(v, str)
        assert v  # non-empty
    else:
        assert hydrolib_version() is None


def test_safe_load_fmmodel_missing_file(tmp_path: Path) -> None:
    """Pointing at a non-existent file yields a non-OK result, no exception."""
    result = safe_load_fmmodel(tmp_path / "does_not_exist.mdu")
    assert isinstance(result, HydrolibLoadResult)
    assert not result.ok
    assert result.error is not None


def test_safe_load_fmmodel_wrong_extension(sample_mdf: Path) -> None:
    """We refuse to feed .mdf to hydrolib-core (it does not understand it)."""
    if not is_hydrolib_available():
        pytest.skip("hydrolib-core is not installed in this environment")
    result = safe_load_fmmodel(sample_mdf)
    assert not result.ok
    assert "only handles .mdu" in (result.error or "")


def test_load_smart_returns_document_for_mdf(sample_mdf: Path) -> None:
    """``.mdf`` files must always come back via the legacy parser."""
    res = load_smart(sample_mdf)
    assert isinstance(res, SmartLoadResult)
    assert res.document is not None
    assert res.document.format.value == "mdf"
    assert res.hydrolib_validated is False
    assert res.hydrolib_error is None


def test_load_smart_falls_back_for_legacy_mdu(legacy_mdu: Path) -> None:
    """Legacy .mdu must still load via our parser, even if hydrolib rejects it."""
    res = load_smart(legacy_mdu)
    assert res.document is not None
    assert res.document.format.value == "mdu"
    # Our parser must keep the legacy keyword even when hydrolib-core would
    # have dropped it.
    general = res.document.section("General")
    assert general is not None
    assert general.get("MDUFormatVersion") is not None
    assert general.get("MDUFormatVersion").value == "1.09"
    if is_hydrolib_available():
        assert res.hydrolib_validated is False
        assert res.hydrolib_error is not None
    else:
        assert res.hydrolib_validated is False
        assert res.hydrolib_error == "hydrolib-core is not installed"


# ---------------------------------------------------------------------------
# Tests that require hydrolib-core (skipped silently otherwise)
# ---------------------------------------------------------------------------


pytestmark_hydrolib = pytest.mark.skipif(
    not is_hydrolib_available(),
    reason="hydrolib-core is not installed",
)


@pytestmark_hydrolib
def test_load_smart_validates_clean_mdu(clean_mdu: Path) -> None:
    """A schema-clean .mdu should load and pass hydrolib-core validation."""
    res = load_smart(clean_mdu)
    assert res.hydrolib_validated is True
    assert res.hydrolib_error is None


@pytestmark_hydrolib
def test_safe_load_returns_typed_model(clean_mdu: Path) -> None:
    """Successful loads expose the typed Pydantic model."""
    result = safe_load_fmmodel(clean_mdu)
    assert result.ok
    model = result.model
    assert model is not None
    assert model.general.program == "D-Flow FM"
    assert model.geometry.bedlevtype == 3
    assert model.time.refdate == 20240101


@pytestmark_hydrolib
def test_fmmodel_set_values_reflects_clean_mdu(clean_mdu: Path) -> None:
    """``fmmodel_set_values`` must surface only the fields that were SET."""
    result = safe_load_fmmodel(clean_mdu)
    assert result.model is not None
    values = fmmodel_set_values(result.model)

    # Sections present in the file should appear with their non-None fields.
    assert "general" in values
    assert values["general"].get("program") == "D-Flow FM"
    assert "geometry" in values
    assert values["geometry"].get("bedlevtype") == 3
    assert "time" in values

    # Sections not mentioned in the .mdu must not show up in the SET view
    # (their defaults stay None at the model level).
    assert "calibration" not in values
    assert "particles" not in values


@pytestmark_hydrolib
def test_fmmodel_section_summary_counts_set_fields(clean_mdu: Path) -> None:
    """``fmmodel_section_summary`` must count only fields that are SET."""
    result = safe_load_fmmodel(clean_mdu)
    assert result.model is not None
    summary = fmmodel_section_summary(result.model)
    # We set 2 fields under [General] in the fixture (program, version) plus
    # any defaults hydrolib autopopulates. Just check the counts are sane.
    assert summary.get("general", 0) >= 2
    assert summary.get("geometry", 0) >= 2
    assert summary.get("time", 0) >= 3


@pytestmark_hydrolib
def test_legacy_mdu_validation_error_is_one_line(legacy_mdu: Path) -> None:
    """Sanitised errors must fit on a single status-bar line."""
    result = safe_load_fmmodel(legacy_mdu)
    assert not result.ok
    err = result.error or ""
    assert "\n" not in err
    assert len(err) <= 240
