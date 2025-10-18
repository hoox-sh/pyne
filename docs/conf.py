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
        (
            "pynescript.ext.pygments.lexers unavailable; Pine Script syntax "
            "highlighting disabled"
        ),
        stacklevel=0,
    )


project = "Pynescript"
author = "Pynescript Maintainers"
copyright = "2024, Pynescript Maintainers"  # noqa: A001
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx_click",
    "myst_parser",
]
autodoc_typehints = "description"
autodoc_mock_imports = [
    "pyasdl",
    "nautilus_trader",
    "tqdm",
]
html_theme = "furo"


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
