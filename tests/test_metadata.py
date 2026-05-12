"""Smoke tests for top-level package metadata."""

from __future__ import annotations

import deltasuite


def test_package_exposes_version() -> None:
    assert isinstance(deltasuite.__version__, str)
    assert deltasuite.__version__


def test_package_exposes_app_constants() -> None:
    assert deltasuite.APP_NAME == "DeltaSuite"
    assert deltasuite.APP_ORG
    assert deltasuite.APP_DOMAIN
