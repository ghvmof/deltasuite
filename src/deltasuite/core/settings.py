"""Application-wide user settings, persisted to TOML on disk."""

from __future__ import annotations

import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Any

import tomli_w
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from deltasuite.core.paths import get_app_paths


class GeneralSettings(BaseModel):
    """High-level UI preferences."""

    model_config = ConfigDict(extra="forbid")

    language: str = Field(default="en", description="UI language code (ISO 639-1).")
    theme: str = Field(default="auto", description="UI theme: 'light', 'dark', or 'auto'.")
    open_last_project_on_startup: bool = True
    show_welcome_screen: bool = True
    check_for_updates: bool = True


class KernelSettings(BaseModel):
    """User-provided overrides for kernel detection."""

    model_config = ConfigDict(extra="forbid")

    extra_paths: list[Path] = Field(
        default_factory=list,
        description="Additional directories scanned before automatic detection.",
    )
    preferred_bin_dir: Path | None = Field(
        default=None,
        description="If set, this directory takes precedence over all other detections.",
    )


class RunnerSettings(BaseModel):
    """Defaults used when invoking simulation kernels."""

    model_config = ConfigDict(extra="forbid")

    default_num_processes: int = Field(default=1, ge=1, le=256)
    keep_log_files: bool = True
    auto_open_results: bool = True
    extra_environment: dict[str, str] = Field(default_factory=dict)


class Settings(BaseModel):
    """Root configuration model persisted to ``settings.toml``."""

    model_config = ConfigDict(extra="forbid")

    general: GeneralSettings = Field(default_factory=GeneralSettings)
    kernels: KernelSettings = Field(default_factory=KernelSettings)
    runner: RunnerSettings = Field(default_factory=RunnerSettings)


def _load_from_disk(path: Path) -> Settings:
    """Read settings from ``path``, returning defaults if the file is missing."""
    if not path.exists():
        logger.debug("No settings file at {}, using defaults", path)
        return Settings()
    try:
        with path.open("rb") as handle:
            raw: dict[str, Any] = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        logger.error("Failed to read settings file {}: {}", path, exc)
        return Settings()
    try:
        return Settings.model_validate(raw)
    except Exception as exc:
        logger.error("Invalid settings file {}: {}. Using defaults.", path, exc)
        return Settings()


def save_settings(settings: Settings, path: Path | None = None) -> Path:
    """Persist ``settings`` to ``path`` (or the default location).

    :returns: The path that was written to.
    """
    target = path or get_app_paths().settings_file
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = settings.model_dump(mode="json")
    payload = _to_toml_safe(payload)
    with target.open("wb") as handle:
        tomli_w.dump(payload, handle)
    logger.debug("Settings saved to {}", target)
    get_settings.cache_clear()
    return target


def _to_toml_safe(obj: Any) -> Any:
    """Recursively normalise an object so that it can be serialised by ``tomli_w``.

    * :class:`Path` instances are converted to strings.
    * ``None`` values are dropped (TOML has no concept of ``null``).
    """
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, dict):
        return {k: _to_toml_safe(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_to_toml_safe(v) for v in obj if v is not None]
    return obj


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached :class:`Settings` instance, loading from disk on first call."""
    return _load_from_disk(get_app_paths().settings_file)
