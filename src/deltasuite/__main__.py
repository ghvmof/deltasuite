"""Module entry point allowing ``python -m deltasuite``."""

from __future__ import annotations

import sys


def main() -> int:
    """Console-script entry point.

    Imports are deferred so that ``deltasuite --help`` does not require the
    optional Qt dependencies to be installed.
    """
    from deltasuite.cli.main import app

    app()
    return 0


if __name__ == "__main__":
    sys.exit(main())
