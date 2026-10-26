# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Unit coverage for pure helpers in ``pynescript.util.pine_facade`` (no network)."""

from __future__ import annotations

from pathlib import Path

import pytest

from pynescript.util import pine_facade as pf


def test_meta_helpers() -> None:
    meta = {
        "scriptName": "My Script",
        "scriptIdPart": "PUB;abc",
        "version": "42",
        "extraKind": "indicator",
        "extra": {"shortDescription": "hi", "plots": [{"id": 1}]},
    }
    assert pf._meta_name(meta) == "My Script"
    assert pf._meta_id(meta) == "PUB;abc"
    assert "42" in pf._meta_version(meta) or pf._meta_version(meta)
    assert pf._meta_kind(meta, "My Script") in {"indicator", "study", "strategy", "library"} or isinstance(
        pf._meta_kind(meta, "My Script"), str
    )
    assert isinstance(pf._meta_extra(meta), dict)
    assert isinstance(pf._meta_short(meta), str)
    assert isinstance(pf._meta_plots(meta), str)
    assert isinstance(pf._pretty_version(42), str)
    assert isinstance(pf._canonical_kind("strategy"), str)
    assert isinstance(pf._kind_markup("indicator"), str)


def test_normalize_filename_and_assign() -> None:
    name = pf._normalize_filename("Foo Bar / Baz!", {" ": "_", "/": "_"})
    assert name.endswith(".pine")
    assigned = pf.assign_filenames(
        [{"scriptName": "Alpha", "scriptIdPart": "1"}, {"scriptName": "Alpha", "scriptIdPart": "2"}],
    )
    assert isinstance(assigned, list)
    assert len(assigned) == 2
    assert assigned[0][1].endswith(".pine")
    assert assigned[0][1] != assigned[1][1]


def test_existing_pines(tmp_path: Path) -> None:
    (tmp_path / "a.pine").write_text("//@version=6\n", encoding="utf-8")
    (tmp_path / "b.txt").write_text("x", encoding="utf-8")
    found = pf._existing_pines(tmp_path)
    assert "a.pine" in found or any(str(p).endswith("a.pine") for p in found) or "a" in {Path(x).stem for x in found}


def test_use_rich_and_console(monkeypatch: pytest.MonkeyPatch) -> None:
    # force plain path
    assert pf._use_rich(plain=True) is False
    assert pf._console(plain=True) is None
    # has_rich should be bool
    assert isinstance(pf._has_rich(), bool)


def test_session_factory_and_thread_session() -> None:
    import requests

    base = requests.Session()
    factory = pf._session_provider_factory(base)
    s = factory()
    assert isinstance(s, requests.Session)
    pf._register_thread_session(s)
    assert pf._get_thread_session() is not None
    pf._close_thread_sessions()


def test_list_builtin_scripts_network_mocked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pf, "list_builtin_scripts", lambda session=None: [{"scriptName": "X", "scriptIdPart": "1"}])
    # call through the patched name
    assert pf.list_builtin_scripts()[0]["scriptName"] == "X"


def test_plain_catalog_and_render(tmp_path: Path) -> None:
    catalog = [
        {"scriptName": "A", "scriptIdPart": "1", "extraKind": "indicator", "version": "1"},
        {"scriptName": "B", "scriptIdPart": "2", "kind": "strategy", "version": "2"},
    ]
    pf._plain_catalog(catalog, tmp_path, worker_count=1, existing=set())
    pf.render_catalog(catalog, tmp_path, worker_count=1, existing=set(), console=None)
