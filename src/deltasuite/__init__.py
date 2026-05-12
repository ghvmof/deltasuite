"""DeltaSuite - Open source desktop suite for Delft3D modeling.

DeltaSuite provides a modern, professional graphical interface to the
open-source Delft3D simulation kernels developed by Deltares.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("deltasuite")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]

APP_NAME: str = "DeltaSuite"
APP_ORG: str = "DeltaSuite"
APP_DOMAIN: str = "deltasuite.org"
