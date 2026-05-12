"""Cross-platform application paths (config, cache, data, logs)."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from platformdirs import PlatformDirs

from deltasuite import APP_NAME, APP_ORG


@dataclass(frozen=True, slots=True)
class AppPaths:
    """Resolved per-user application directories.

    Follows the platform conventions:

    * Windows ``%APPDATA%\\DeltaSuite\\DeltaSuite\\``
    * macOS ``~/Library/Application Support/DeltaSuite/``
    * Linux ``~/.config/DeltaSuite/`` and ``~/.cache/DeltaSuite/``
    """

    config_dir: Path
    cache_dir: Path
    data_dir: Path
    log_dir: Path

    @property
    def settings_file(self) -> Path:
        """Absolute path to the user's settings TOML file."""
        return self.config_dir / "settings.toml"

    @property
    def recent_projects_file(self) -> Path:
        """Absolute path to the recent projects list."""
        return self.config_dir / "recent_projects.toml"

    def ensure(self) -> None:
        """Create all directories if they do not exist."""
        for path in (self.config_dir, self.cache_dir, self.data_dir, self.log_dir):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_app_paths() -> AppPaths:
    """Return the singleton :class:`AppPaths` for the current user.

    The first call resolves the platform-specific directories, subsequent
    calls return the cached instance.
    """
    dirs = PlatformDirs(appname=APP_NAME, appauthor=APP_ORG, roaming=True)
    paths = AppPaths(
        config_dir=Path(dirs.user_config_dir),
        cache_dir=Path(dirs.user_cache_dir),
        data_dir=Path(dirs.user_data_dir),
        log_dir=Path(dirs.user_log_dir),
    )
    paths.ensure()
    return paths
