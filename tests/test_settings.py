"""Tests for the user settings model and its TOML round-trip."""

from __future__ import annotations

from pathlib import Path

from deltasuite.core.settings import GeneralSettings, Settings, save_settings


def test_settings_defaults_are_sensible() -> None:
    s = Settings()
    assert s.general.language == "en"
    assert s.general.theme == "auto"
    assert s.general.show_welcome_screen is True
    assert s.runner.default_num_processes == 1
    assert s.kernels.extra_paths == []


def test_settings_can_be_saved_and_reloaded(tmp_path: Path) -> None:
    target = tmp_path / "settings.toml"
    payload = Settings(general=GeneralSettings(language="es", theme="dark"))
    save_settings(payload, target)
    assert target.is_file()

    import tomllib

    with target.open("rb") as fh:
        data = tomllib.load(fh)
    assert data["general"]["language"] == "es"
    assert data["general"]["theme"] == "dark"


def test_settings_extra_fields_are_rejected() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings.model_validate({"general": {"unknown_key": True}})
