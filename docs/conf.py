"""Sphinx configuration for DeltaSuite documentation."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import deltasuite  # noqa: E402

# -- Project information -----------------------------------------------------

project = "DeltaSuite"
author = "DeltaSuite contributors"
copyright = f"{datetime.now().year}, {author}"
release = deltasuite.__version__
version = release

# -- General configuration ---------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx.ext.todo",
    "sphinx_copybutton",
    "myst_parser",
    "autoapi.extension",
]

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

master_doc = "index"
language = "en"
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# Napoleon
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = False

# AutoAPI
autoapi_type = "python"
autoapi_dirs = [str(ROOT / "src" / "deltasuite")]
autoapi_root = "api"
autoapi_options = [
    "members",
    "undoc-members",
    "show-inheritance",
    "show-module-summary",
    "imported-members",
]
autoapi_python_class_content = "both"
autoapi_keep_files = False

# Intersphinx
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "PySide6": ("https://doc.qt.io/qtforpython-6/", None),
    "numpy": ("https://numpy.org/doc/stable/", None),
    "pydantic": ("https://docs.pydantic.dev/latest/", None),
}

# Todo
todo_include_todos = True

# -- HTML output -------------------------------------------------------------

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
html_title = f"{project} v{release}"
html_show_sphinx = False
html_show_copyright = True
html_theme_options = {
    "navigation_depth": 4,
    "collapse_navigation": False,
    "sticky_navigation": True,
    "logo_only": False,
    "prev_next_buttons_location": "both",
}

# -- Markdown ----------------------------------------------------------------

myst_enable_extensions = [
    "deflist",
    "colon_fence",
    "smartquotes",
    "tasklist",
    "linkify",
]
