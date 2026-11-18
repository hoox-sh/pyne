# Copyright (C) 2024-2026 jango_blockchained
#
# This file is part of pynescript.
#
# pynescript is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pynescript is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with pynescript.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Wheel contents and the ``datafeed`` extra.

The wheel target used to list only ``src/pynescript``, so a pip install could
not ``import backend`` even though ``[pro]`` installed Flask. The ``datafeed``
extra was only ``ccxt``, while ``backend.datafeed_app`` imports the web stack.
"""

from __future__ import annotations

import ast
import re
import sys
import zipfile

from email import message_from_bytes
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[1]

# Import root -> PyPI distribution. Only names the datafeed closure can reach
# are required; the map exists so ``dotenv`` is not recorded as a distribution
# named ``dotenv``.
_DIST_FOR_IMPORT = {
    "ccxt": "ccxt",
    "dotenv": "python-dotenv",
    "flask": "flask",
    "flask_cors": "flask-cors",
    "flask_sock": "flask-sock",
    "gevent": "gevent",
    "gunicorn": "gunicorn",
    "lsprotocol": "lsprotocol",
    "matplotlib": "matplotlib",
    "numba": "numba",
    "numpy": "numpy",
    "redis": "redis",
    "simple_websocket": "simple-websocket",
}

# Named by the packaging card: do not copy these from ``[pro]`` unless the
# datafeed import graph actually reaches them.
_PRO_STACK_NOT_ON_DATAFEED = ("matplotlib", "numba", "redis")

_DATAFEED_MODULES = (
    "backend/__init__.py",
    "backend/api/__init__.py",
    "backend/api/datafeed.py",
    "backend/datafeed_app.py",
)

_SDIST_EXCLUDES = (
    '"/.env"',
    '"/.env.*"',
    '"/scripts/build/.metadata.key"',
    '"/.oo"',
    '"/tests/data"',
)


def _normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _resolve_backend(module: str) -> Path | None:
    if module != "backend" and not module.startswith("backend."):
        return None
    parts = module.split(".")[1:]
    candidate = REPO.joinpath("backend", *parts)
    module_file = candidate.with_suffix(".py")
    if module_file.is_file():
        return module_file
    init = candidate / "__init__.py"
    if init.is_file():
        return init
    return None


def _package_of(path: Path) -> str:
    # Drop ``__init__.py`` or the module filename; what remains is the package.
    return ".".join(path.relative_to(REPO).parts[:-1])


def _absolute_module(path: Path, node: ast.ImportFrom) -> str | None:
    if node.level == 0:
        return node.module
    parts = _package_of(path).split(".")
    drop = node.level - 1
    if drop:
        if drop > len(parts):
            return None
        parts = parts[:-drop]
    if node.module:
        parts.extend(node.module.split("."))
    return ".".join(parts) if parts else None


def _datafeed_imports() -> set[str]:
    """Third-party distributions imported by ``backend.datafeed_app`` and the backend modules it reaches."""
    stdlib = sys.stdlib_module_names
    pending = [REPO / "backend" / "datafeed_app.py"]
    seen: set[Path] = set()
    found: set[str] = set()

    def consider(module: str) -> None:
        root = module.split(".", 1)[0]
        if root == "backend":
            resolved = _resolve_backend(module)
            if resolved is not None:
                pending.append(resolved)
            return
        if root in {"pynescript", "__future__"} or root in stdlib:
            return
        dist = _DIST_FOR_IMPORT.get(root)
        if dist is None:
            msg = f"unmapped third-party import {module!r} on the datafeed path"
            raise AssertionError(msg)
        found.add(dist)

    while pending:
        path = pending.pop()
        if path in seen:
            continue
        seen.add(path)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    consider(alias.name)
            elif isinstance(node, ast.ImportFrom) and (node.module or node.level):
                module = _absolute_module(path, node)
                if not module:
                    continue
                consider(module)
                if module == "backend" or module.startswith("backend."):
                    for alias in node.names:
                        consider(f"{module}.{alias.name}")
    return found


def _requires_by_extra(wheel: Path) -> dict[str, dict[str, str]]:
    with zipfile.ZipFile(wheel) as archive:
        metadata_name = next(name for name in archive.namelist() if name.endswith(".dist-info/METADATA"))
        message = message_from_bytes(archive.read(metadata_name))
    grouped: dict[str, dict[str, str]] = {}
    for requirement in message.get_all("Requires-Dist") or []:
        marker = requirement.split(";", 1)[1] if ";" in requirement else ""
        matched = re.search(r"""extra\s*==\s*['"]([^'"]+)['"]""", marker)
        if matched is None:
            continue
        core = requirement.split(";", 1)[0].strip()
        name_match = re.match(r"^([A-Za-z0-9][A-Za-z0-9_.-]*)\s*(.*)$", core)
        if name_match is None:
            msg = f"unparsed Requires-Dist entry: {requirement}"
            raise AssertionError(msg)
        name = _normalize_name(name_match.group(1))
        grouped.setdefault(matched.group(1), {})[name] = name_match.group(2).strip()
    return grouped


def _wheel_members(wheel: Path) -> set[str]:
    with zipfile.ZipFile(wheel) as archive:
        return {name.replace("\\", "/") for name in archive.namelist()}


def _leaked(member: str) -> bool:
    parts = member.split("/")
    base = parts[-1]
    if base == ".env" or base.startswith(".env"):
        return True
    if base == ".metadata.key" or base.endswith(".metadata.key"):
        return True
    if ".oo" in parts:
        return True
    return any(parts[index] == "tests" and parts[index + 1] == "data" for index in range(len(parts) - 1))


@pytest.fixture(scope="module")
def built_wheel(tmp_path_factory: pytest.TempPathFactory) -> Path:
    pytest.importorskip("hatchling")
    from hatchling.builders.wheel import WheelBuilder

    out = tmp_path_factory.mktemp("wheel")
    builder = WheelBuilder(str(REPO))
    return Path(next(builder.build(directory=str(out), versions=["standard"])))


def test_wheel_contains_backend_and_not_secrets(built_wheel: Path) -> None:
    members = _wheel_members(built_wheel)
    missing = [path for path in _DATAFEED_MODULES if path not in members]
    assert not missing, missing
    backend_sources = sorted(
        path.relative_to(REPO).as_posix()
        for path in (REPO / "backend").rglob("*.py")
        if "__pycache__" not in path.parts
    )
    unpackaged = [path for path in backend_sources if path not in members]
    assert not unpackaged, unpackaged
    assert "pynescript/__init__.py" in members
    dist_info = next(name.split("/", 1)[0] for name in members if name.endswith(".dist-info/METADATA"))
    allowed = ("pynescript/", "backend/", f"{dist_info}/")
    foreign = [name for name in members if name and not name.startswith(allowed)]
    assert not foreign, foreign
    leaked = [name for name in members if _leaked(name)]
    assert not leaked, leaked


def test_datafeed_extra_matches_imported_web_packages(built_wheel: Path) -> None:
    discovered = _datafeed_imports()
    # flask is a hard requirement of the gateway, not an optional walker miss.
    assert "flask" in discovered
    assert "flask-sock" in discovered
    assert "ccxt" in discovered
    by_extra = _requires_by_extra(built_wheel)
    datafeed = by_extra["datafeed"]
    assert set(datafeed) == discovered
    for name, spec in datafeed.items():
        if name in by_extra["pro"]:
            assert spec == by_extra["pro"][name], (name, spec, by_extra["pro"][name])
    assert datafeed["ccxt"] == by_extra["data"]["ccxt"]
    for banned in _PRO_STACK_NOT_ON_DATAFEED:
        assert banned not in discovered
        assert banned not in datafeed


def test_sdist_excludes_still_block_secrets() -> None:
    text = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    missing = [pattern for pattern in _SDIST_EXCLUDES if pattern not in text]
    assert not missing, missing
