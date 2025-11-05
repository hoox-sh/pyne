from __future__ import annotations

import pathlib
import shutil
import sys
import warnings

from sphinx.application import Sphinx  # type: ignore[import]
from sphinx.ext import apidoc  # type: ignore[import]
from sphinx.highlighting import lexers as sphinx_lexers  # type: ignore[import]


sphinx_apidoc_main = apidoc.main


DOCS_DIR = pathlib.Path(__file__).parent
PROJECT_DIR = DOCS_DIR.parent
SRC_DIR = PROJECT_DIR / "src"
APIDOC_EXCLUDES = [
    SRC_DIR / "pynescript/ast/grammar/antlr4/generated",
    SRC_DIR / "pynescript/ast/grammar/asdl/generated",
]

sys.path.insert(0, str(SRC_DIR))

try:
    from pynescript.ext.pygments.lexers import PinescriptLexer

    sphinx_lexers["pinescript"] = PinescriptLexer()
except ModuleNotFoundError:
    warnings.warn(
        ("pynescript.ext.pygments.lexers unavailable; Pine Script™ syntax highlighting disabled"),
        stacklevel=0,
    )


project = "Pynescript"
author = "Pynescript Maintainers"
copyright = "2024, Pynescript Maintainers"  # noqa: A001
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx_click",
    "myst_parser",
]

# Autodoc settings for comprehensive coverage
autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "special-members": "__init__",
    "undoc-members": True,
    "exclude-members": "__weakref__",
    "show-inheritance": True,
}
autodoc_typehints = "description"
autodoc_mock_imports = [
    "pyasdl",
    "nautilus_trader",
    "tqdm",
]

# Autosummary settings
autosummary_generate = True
autosummary_generate_overwrite = True

# Napoleon settings
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = True
napoleon_use_admonition_for_notes = True
napoleon_use_admonition_for_references = False
napoleon_use_ivar = True
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_preprocess_types = True
napoleon_attr_annotations = True

# Intersphinx mapping
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

html_theme = "furo"
html_title = "Pynescript Documentation"
html_static_path = []


def run_apidoc(_) -> None:
    output_path = PROJECT_DIR / "docs/apidoc"
    module_path = SRC_DIR / "pynescript"

    if output_path.exists():
        shutil.rmtree(output_path)

    args = [
        "--force",
        "--separate",
        "--ext-autodoc",
        "--output-dir",
        str(output_path),
        str(module_path),
    ]

    sphinx_apidoc_main(args + [str(path) for path in APIDOC_EXCLUDES])


def setup(app: Sphinx) -> None:
    app.connect("builder-inited", run_apidoc)
