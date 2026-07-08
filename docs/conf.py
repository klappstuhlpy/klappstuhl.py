# Configuration file for the Sphinx documentation builder.
#
# Full reference: https://www.sphinx-doc.org/en/master/usage/configuration.html

from __future__ import annotations

import os
import sys
from importlib import metadata

# Make the package importable by autodoc when building from a source checkout
# (on Read the Docs the package is pip-installed, so this is just a local aid).
sys.path.insert(0, os.path.abspath(".."))

# -- Project information ------------------------------------------------------

project = "klappstuhl.py"
author = "klappstuhlpy"
copyright = f"2026, {author}"

try:
    release = metadata.version("klappstuhl.py")
except metadata.PackageNotFoundError:  # not installed — building from source tree
    release = "0.0.0+unknown"
# The short X.Y version.
version = ".".join(release.split(".")[:2])

# -- General configuration ----------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",       # pull docstrings straight from the source
    "sphinx.ext.napoleon",      # understand NumPy-style "Parameters" sections
    "sphinx.ext.intersphinx",   # cross-link to Python / aiohttp docs
    "sphinx.ext.viewcode",      # add "[source]" links next to each object
    "sphinx.ext.autosummary",   # generate the summary tables
    "sphinx_copybutton",        # a copy button on code blocks
]

autosummary_generate = True
templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- autodoc ------------------------------------------------------------------

autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "show-inheritance": True,
    "undoc-members": False,
}
autodoc_typehints = "description"          # render type hints in the body, not the signature
autodoc_typehints_description_target = "documented"
autodoc_member_order = "bysource"
autoclass_content = "class"                # merge the class docstring only (not __init__)
autodoc_preserve_defaults = True

# -- napoleon -----------------------------------------------------------------

napoleon_google_docstring = False
napoleon_numpy_docstring = True
napoleon_use_param = True
napoleon_use_rtype = True

# -- intersphinx --------------------------------------------------------------

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "aiohttp": ("https://docs.aiohttp.org/en/stable", None),
}

# -- HTML output --------------------------------------------------------------

html_theme = "furo"
html_title = f"klappstuhl.py {release}"
html_static_path = ["_static"]
html_logo = "_static/logo.png"
html_favicon = "_static/logo.png"

html_theme_options = {
    "source_repository": "https://github.com/klappstuhlpy/klappstuhl.py",
    "source_branch": "main",
    "source_directory": "docs/",
}
