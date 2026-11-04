"""Sphinx configuration for the landgraph documentation."""

import os
import sys
from pathlib import Path

# Make the package importable without installing it.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

# app.py builds the app at import time and reads DATABASE_URL. The engine is lazy,
# so a placeholder is enough: autodoc imports the module but never connects.
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://docs:docs@localhost/docs")

project = "landgraph"
author = "Akshat"
copyright = "2026, Akshat"

extensions = [
    "sphinx.ext.autodoc",  # pull documentation from docstrings
    "sphinx.ext.napoleon",  # understand Google-style Args/Returns/Raises
    "sphinx.ext.viewcode",  # "[source]" links next to each function
    "sphinx_immaterial",  # Material theme
]

napoleon_google_docstring = True
napoleon_numpy_docstring = False
autodoc_typehints = "description"  # show types next to each argument
autodoc_member_order = "bysource"  # same order as in the code
autodoc_default_options = {"members": True, "show-inheritance": False}

html_theme = "sphinx_immaterial"
html_title = "landgraph"
html_theme_options = {
    "repo_url": "https://github.com/AkshatDev/landgraph",
    "repo_name": "landgraph",
    "palette": [
        {
            "media": "(prefers-color-scheme: light)",
            "scheme": "default",
            "primary": "green",
            "toggle": {"icon": "material/weather-night", "name": "Dark mode"},
        },
        {
            "media": "(prefers-color-scheme: dark)",
            "scheme": "slate",
            "primary": "green",
            "toggle": {"icon": "material/weather-sunny", "name": "Light mode"},
        },
    ],
    "features": ["navigation.sections", "navigation.top", "search.highlight"],
}
