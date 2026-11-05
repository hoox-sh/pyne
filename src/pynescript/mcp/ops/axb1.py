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

"""AXB1 golden-vector verification as an MCP op (no MCP SDK required).

Mirrors the encoder half of ``tests/test_axb1.py``: each vector carries a
language-neutral frame spec plus the exact little-endian hex the encoder
must emit — the cross-repo wire contract with AXIS
(``axis/tests/hp/axb1-vectors.json``). The mapper below is intentionally the
same shape as the test's ``frame_from_spec`` / encode dispatch so a drift
in either direction fails loudly here too.
"""

from __future__ import annotations

import json

from pathlib import Path
from typing import Any

import pynescript

from pynescript.mcp.serialize import fail
from pynescript.mcp.serialize import jsonable
from pynescript.mcp.serialize import ok
from pynescript.runtime import axb1


def bundled_vectors_path() -> Path | None:
    """Repo-bundled golden vectors (editable checkout) or ``None``."""
    root = Path(pynescript.__file__).resolve().parents[2]
    candidate = root / "tests" / "data" / "axb1-vectors.json"
    return candidate if candidate.is_file() else None


def _tip_of(raw: dict) -> dict:
    mask = 0
    for name in raw.get("mask") or []:
        mask |= int(axb1.TipMask[name])
    tip: dict = {"mask": mask, "flags": int(raw.get("flags") or 0)}
    if raw.get("time_s") is not None:
        tip["time_s"] = int(raw["time_s"])
    if raw.get("volume") is not None:
        tip["volume"] = float(raw["volume"])
    for field in ("open", "high", "low", "close"):
        if raw.get(field) is not None:
            tip[field] = int(raw[field])
    return tip


def _kind_of(name: str) -> int:
    return int(axb1.ValueKind.PriceTicks if name == "price_ticks" else axb1.ValueKind.UnitFloat64)


def _ohlcv_of(raw: dict, *, columns: bool) -> dict:
    out: dict = {}
    for field in ("open", "high", "low", "close", "volume"):
        values = raw[field]
        if field == "volume":
            out[field] = [float(v) for v in values] if columns else float(values)
        else:
            out[field] = [int(v) for v in values] if columns else int(values)
    return out


def frame_from_spec(raw: dict) -> dict:
    """Vector spec (snake_case, decimal-string ints) → encoder dispatch dict."""
    header = axb1.Header(
        seq=int(raw["seq"]),
        sub_id_hash=int(raw["sub_id_hash"]),
        session_hash=int(raw["session_hash"]),
        ts_ms=int(raw["ts_ms"]),
        hdr_flags=int(raw.get("hdr_flags") or 0),
    )
    rest = {
        k: v for k, v in raw.items() if k not in ("opcode", "seq", "sub_id_hash", "session_hash", "ts_ms", "hdr_flags")
    }
    opcode = str(raw["opcode"])
    if opcode in ("HEARTBEAT", "UNCHANGED"):
        return {"fn": opcode, "header": header}
    if opcode == "STATUS":
        return {
            "fn": opcode,
            "header": header,
            "status_code": rest["status_code"],
            "detail": rest.get("detail", ""),
            "have": int(rest["have"]),
            "need": int(rest["need"]),
        }
    if opcode == "TIP_UPDATE":
        return {"fn": opcode, "header": header, "tip": _tip_of(rest)}
    if opcode == "APPEND_BAR":
        return {
            "fn": opcode,
            "header": header,
            "price_scale": int(rest["price_scale"]),
            "closed_index": int(rest["closed_index"]),
            "closed_time": int(rest["closed_time"]),
            "ohlcv": _ohlcv_of(rest, columns=False),
            "tip": _tip_of(rest["tip"]),
        }
    if opcode == "CLOSE_VERIFY":
        return {
            "fn": opcode,
            "header": header,
            "index": int(rest["index"]),
            "time_s": int(rest["time_s"]),
            "ohlcv": _ohlcv_of(rest, columns=False),
        }
    if opcode == "PLOT_TIP":
        return {
            "fn": opcode,
            "header": header,
            "plots": [
                {
                    "key_hash": int(p["key_hash"]),
                    "kind": _kind_of(p["kind"]),
                    "ticks": int(p["ticks"]) if p.get("ticks") is not None else None,
                    "value": float(p["value"]) if p.get("value") is not None else None,
                }
                for p in rest["plots"]
            ],
        }
    if opcode == "SNAPSHOT_OHLCV":
        return {
            "fn": opcode,
            "header": header,
            "price_scale": int(rest["price_scale"]),
            "count": int(rest["count"]),
            "closed_upto": int(rest["closed_upto"]),
            "hot_from_index": int(rest["hot_from_index"]),
            "time_s": [int(t) for t in rest["time_s"]],
            "flags": [int(f) for f in rest["flags"]],
            "ohlcv": _ohlcv_of(rest, columns=True),
        }
    if opcode == "SNAPSHOT_PLOTS":
        return {
            "fn": opcode,
            "header": header,
            "count": int(rest["count"]),
            "closed_upto": int(rest["closed_upto"]),
            "times": [int(t) for t in rest["times"]] if rest.get("times") is not None else None,
            "plots": [
                {
                    "key": p["key"],
                    "kind": _kind_of(p["kind"]),
                    "ticks": [int(t) for t in p["ticks"]] if p.get("ticks") is not None else None,
                    "values": [float(v) for v in p["values"]] if p.get("values") is not None else None,
                }
                for p in rest["plots"]
            ],
        }
    if opcode == "ERROR":
        return {
            "fn": opcode,
            "header": header,
            "code": rest["code"],
            "message": rest["message"],
            "retryable": bool(rest["retryable"]),
        }
    if opcode == "JSON_BLOB":
        return {"fn": opcode, "header": header, "json_text": rest["json"]}
    if opcode == "APPEND_BARS":
        return {
            "fn": opcode,
            "header": header,
            "price_scale": int(rest["price_scale"]),
            "count": int(rest["count"]),
            "closed_upto": int(rest["closed_upto"]),
            "closed_index": int(rest["closed_index"]),
            "time_s": [int(t) for t in rest["time_s"]],
            "flags": [int(f) for f in rest["flags"]],
            "ohlcv": _ohlcv_of(rest, columns=True),
            "tip": _tip_of(rest["tip"]),
        }
    raise ValueError(f"unknown golden-vector opcode {opcode}")


def encode_frame_spec(spec: dict) -> bytes:
    """Dispatch like the AXIS ``encodeFrame`` switch, one encode_* per opcode."""
    fn = spec["fn"]
    header = spec["header"]
    if fn == "HEARTBEAT":
        return axb1.encode_heartbeat(header)
    if fn == "UNCHANGED":
        return axb1.encode_unchanged(header)
    if fn == "STATUS":
        return axb1.encode_status(
            header,
            status_code=spec["status_code"],
            detail=spec["detail"],
            have=spec["have"],
            need=spec["need"],
        )
    if fn == "TIP_UPDATE":
        return axb1.encode_tip_update(header, spec["tip"])
    if fn == "APPEND_BAR":
        return axb1.encode_append_bar(
            header,
            price_scale=spec["price_scale"],
            closed_index=spec["closed_index"],
            closed_time=spec["closed_time"],
            ohlcv=spec["ohlcv"],
            tip=spec["tip"],
        )
    if fn == "CLOSE_VERIFY":
        return axb1.encode_close_verify(header, index=spec["index"], time_s=spec["time_s"], ohlcv=spec["ohlcv"])
    if fn == "PLOT_TIP":
        return axb1.encode_plot_tip(header, spec["plots"])
    if fn == "SNAPSHOT_OHLCV":
        return axb1.encode_snapshot_ohlcv(
            header,
            price_scale=spec["price_scale"],
            count=spec["count"],
            closed_upto=spec["closed_upto"],
            hot_from_index=spec["hot_from_index"],
            time_s=spec["time_s"],
            flags=spec["flags"],
            ohlcv=spec["ohlcv"],
        )
    if fn == "SNAPSHOT_PLOTS":
        return axb1.encode_snapshot_plots(
            header,
            count=spec["count"],
            closed_upto=spec["closed_upto"],
            times=spec["times"],
            plots=spec["plots"],
        )
    if fn == "ERROR":
        return axb1.encode_error(header, code=spec["code"], message=spec["message"], retryable=spec["retryable"])
    if fn == "JSON_BLOB":
        return axb1.encode_json_blob(header, spec["json_text"])
    if fn == "APPEND_BARS":
        return axb1.encode_append_bars(
            header,
            price_scale=spec["price_scale"],
            count=spec["count"],
            closed_upto=spec["closed_upto"],
            closed_index=spec["closed_index"],
            time_s=spec["time_s"],
            flags=spec["flags"],
            ohlcv=spec["ohlcv"],
            tip=spec["tip"],
        )
    raise ValueError(f"unknown encoder dispatch {fn}")


def _load_doc(vectors_path: str | None, vectors: Any | None) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Return ``(doc, error_payload)``; exactly one is non-``None``."""
    if vectors is not None:
        if isinstance(vectors, str):
            try:
                vectors = json.loads(vectors)
            except json.JSONDecodeError as exc:
                return None, fail(f"invalid vectors JSON: {exc}", kind="args")
        if isinstance(vectors, list):
            return {"version": 1, "vectors": vectors, "hash_checks": []}, None
        if isinstance(vectors, dict):
            return vectors, None
        return None, fail("vectors must be a JSON object, array, or JSON text", kind="args")
    path = Path(vectors_path) if vectors_path else bundled_vectors_path()
    if path is None:
        return None, fail(
            "no bundled vectors in this install; pass vectors_path or inline vectors",
            kind="io",
        )
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except (OSError, json.JSONDecodeError) as exc:
        return None, fail(f"cannot load vectors from {path}: {exc}", kind="io")


def _reject_rules() -> dict[str, bool]:
    """Codec reject rules every encoder must enforce (v1 audit, hp2 E1)."""
    probes: dict[str, Any] = {}

    def _expect(name: str, fn: Any) -> None:
        try:
            fn()
        except ValueError:
            probes[name] = True
        except Exception:
            probes[name] = False
        else:
            probes[name] = False

    _expect(
        "compressed_bit_rejected",
        lambda: axb1.encode_envelope(axb1.Header(hdr_flags=axb1.AXB1_HDR_COMPRESSED), b""),
    )
    _expect("unaligned_payload_rejected", lambda: axb1.encode_envelope(axb1.Header(), b"abc"))
    _expect(
        "oversized_payload_rejected",
        lambda: axb1.encode_envelope(axb1.Header(), b"\x00" * (axb1.AXB1_MAX_PAYLOAD + 4)),
    )
    _expect(
        "tip_requires_time_bit",
        lambda: axb1.encode_tip_update(axb1.Header(), {"mask": int(axb1.TipMask.CLOSE), "flags": 1, "close": 1}),
    )

    def _bad_scale() -> None:
        axb1.encode_snapshot_ohlcv(
            axb1.Header(),
            price_scale=13,
            count=0,
            closed_upto=0,
            hot_from_index=0,
            time_s=[],
            flags=[],
            ohlcv={"open": [], "high": [], "low": [], "close": [], "volume": []},
        )

    _expect("price_scale_bounds_enforced", _bad_scale)
    return probes


def verify_axb1_vectors(
    vectors_path: str | None = None,
    vectors: Any | None = None,
    only: Any | None = None,
) -> dict[str, Any]:
    """Verify the AXB1 encoder against golden vectors (hex-exact).

    ``vectors`` is inline JSON (doc or bare array) or ``vectors_path`` points
    at a vectors file; both default to the bundled
    ``tests/data/axb1-vectors.json``. ``only`` selects vectors by name
    (string or array of strings).
    """
    doc, err = _load_doc(vectors_path, vectors)
    if err is not None or doc is None:
        return err if err is not None else fail("no vectors document", kind="io")
    wanted = None
    if only is not None:
        wanted = {only} if isinstance(only, str) else set(only)
    failures: list[dict[str, Any]] = []
    checked = 0
    for vector in doc.get("vectors", []):
        name = str(vector.get("name", "?"))
        if wanted is not None and name not in wanted:
            continue
        checked += 1
        try:
            actual = encode_frame_spec(frame_from_spec(vector["frame"])).hex()
        except Exception as exc:
            failures.append({"name": name, "error": str(exc)[:300]})
            continue
        if actual != vector.get("hex"):
            failures.append(
                {
                    "name": name,
                    "expected": str(vector.get("hex", ""))[:160],
                    "actual": actual[:160],
                }
            )
    hash_failures: list[dict[str, Any]] = []
    for check in doc.get("hash_checks", []):
        try:
            got = axb1.fnv1a32(str(check["input"]))
        except Exception as exc:
            hash_failures.append({"input": check.get("input"), "error": str(exc)[:200]})
            continue
        if got != check.get("fnv1a32"):
            hash_failures.append({"input": check.get("input"), "expected": check.get("fnv1a32"), "actual": got})
    rejects = _reject_rules()
    payload = ok(
        version=doc.get("version", 1),
        vectors_total=len(doc.get("vectors", [])),
        vectors_checked=checked,
        vectors_passed=checked - len(failures),
        vectors_failed=len(failures),
        failures=failures,
        hash_checks={
            "total": len(doc.get("hash_checks", [])),
            "failed": len(hash_failures),
            "failures": hash_failures,
        },
        reject_rules=rejects,
    )
    if failures or hash_failures or not all(rejects.values()):
        payload["ok"] = False
        payload["error"] = (
            f"AXB1 mismatch: {len(failures)} vector(s), "
            f"{len(hash_failures)} hash(es), "
            f"{sum(1 for v in rejects.values() if not v)} reject rule(s) failing"
        )
    return jsonable(payload)
