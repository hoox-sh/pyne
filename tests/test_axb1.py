# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later

"""AXB1 v1 golden-vector suite + ``WS /ws/live`` ``encoding: "axb1"`` negotiation.

The 12 vectors + hash checks in ``tests/data/axb1-vectors.json`` are the
cross-repo wire contract with AXIS (``axis/tests/hp/axb1-vectors.json``): each
vector carries a language-neutral frame spec (int64 as decimal strings, masks
as name arrays) and the exact little-endian hex the encoder must emit.
``frame_from_spec`` mirrors the AXIS codec test's mapper
(``axis/tests/hp/axb1-codec.test.ts``).

The mapping/wiring half is socket-free: :func:`map_live_frame` is a pure
JSON→AXB1 projection, and the :class:`LiveConnection` tests drive the
connection's real subscribe/hub paths with a fake sender — with
``encoding: "axb1"`` negotiated, mappable frames leave as ``b"AXB1"`` bytes;
without the flag (or when a frame is unmappable) everything stays JSON, which
is the compatibility guarantee.
"""

from __future__ import annotations

import json
import os
import sys

from pathlib import Path


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from backend.api.live_ws import LiveConnection
from backend.api.live_ws import LiveRegistry
from backend.api.live_ws import make_close
from backend.api.live_ws import make_delta
from backend.api.live_ws import make_status
from backend.api.live_ws import map_live_frame
from pynescript.runtime import axb1


VECTORS = json.loads((Path(__file__).parent / "data" / "axb1-vectors.json").read_text(encoding="utf-8"))

META = {"exchange": "binance", "market": "spot", "symbol": "btc/usdt", "interval": "1m"}
KEY_TEXT = "binance|spot|BTC/USDT|1m"
SUB_ID = "series:binance|spot|BTC/USDT|1m"


# -- golden-vector mapper (mirrors axis/tests/hp/axb1-codec.test.ts) ------


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
    raise AssertionError(f"unknown golden-vector opcode {opcode}")


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
    raise AssertionError(f"unknown encoder dispatch {fn}")


# -- encoder: golden vectors + reject rules -------------------------------


@pytest.mark.parametrize("vector", VECTORS["vectors"], ids=[v["name"] for v in VECTORS["vectors"]])
def test_encoder_matches_golden_vector(vector):
    assert encode_frame_spec(frame_from_spec(vector["frame"])) == bytes.fromhex(vector["hex"])


def test_fnv1a32_matches_shared_hash_checks():
    assert axb1.fnv1a32("") == 2166136261
    assert axb1.fnv1a32("a") == 3826002220
    assert axb1.fnv1a32("foobar") == 3214735720
    for check in VECTORS["hash_checks"]:
        assert axb1.fnv1a32(check["input"]) == check["fnv1a32"]


def test_envelope_rejects_compression_bit():
    with pytest.raises(ValueError):
        axb1.encode_envelope(axb1.Header(hdr_flags=axb1.AXB1_HDR_COMPRESSED), b"")


def test_envelope_rejects_unaligned_payload():
    with pytest.raises(ValueError):
        axb1.encode_envelope(axb1.Header(), b"abc")


def test_envelope_rejects_oversized_payload():
    with pytest.raises(ValueError):
        axb1.encode_envelope(axb1.Header(), b"\x00" * (axb1.AXB1_MAX_PAYLOAD + 4))


def test_tip_update_requires_time_bit():
    with pytest.raises(ValueError):
        axb1.encode_tip_update(axb1.Header(), {"mask": int(axb1.TipMask.CLOSE), "flags": 1, "close": 1})


def test_price_scale_bounds_enforced():
    with pytest.raises(ValueError):
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
    with pytest.raises(ValueError):
        axb1.price_to_ticks(1.0, -1)


def test_price_to_ticks_uses_js_half_up_rounding():
    # Python's round() is banker's (round(2.5) == 2); JS Math.round(2.5) == 3.
    assert axb1.price_to_ticks(2.5e-8, 8) == 3
    assert axb1.price_to_ticks(60425.5, 8) == 6042550000000


# -- map_live_frame: pure JSON → AXB1 projection --------------------------

# The last bar of the 10-bar series window used by the mapping/wiring tests.
BARS = [
    {"time": 1_700_000_000 + i * 60, "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 3.0}
    for i in range(10)
]
LAST_TIME = BARS[-1]["time"]


def _frame(mtype: str, payload: dict, *, req_id=SUB_ID, seq: int = 1, session_id: str = "sess-7f3a") -> dict:
    frame: dict = {"type": mtype, "sessionId": session_id, "seq": seq, "payload": payload}
    if req_id is not None:
        frame["id"] = req_id
    return frame


def test_map_status_live_becomes_binary():
    out = map_live_frame(_frame("status", {"code": "live", "message": "live/1 ok", "have": 5000, "need": 5000}, seq=3))
    assert isinstance(out, bytes)
    assert out[:4] == b"AXB1"
    assert out[5] == int(axb1.Axb1Opcode.STATUS)


def test_map_idle_status_stays_json():
    assert map_live_frame(_frame("status", {"code": "idle", "message": "waiting"})) is None


def test_map_series_full_becomes_snapshot():
    payload = {"seriesKey": KEY_TEXT, "count": len(BARS), "closed_upto": LAST_TIME, "bars": BARS}
    out = map_live_frame(_frame("full", payload))
    assert isinstance(out, bytes)
    assert out[5] == int(axb1.Axb1Opcode.SNAPSHOT_OHLCV)


def test_map_script_full_stays_json():
    payload = {
        "seriesKey": KEY_TEXT,
        "count": 2,
        "closed_upto": 0,
        "plots": [[1.0, 2.0]],
        "series": {"a": [1.0, 2.0]},
    }
    assert map_live_frame(_frame("full", payload)) is None


def test_map_script_full_stays_json_in_basic_mode():
    payload = {
        "seriesKey": KEY_TEXT,
        "count": 2,
        "closed_upto": 0,
        "plots": [[1.0, 2.0]],
        "series": {"a": [1.0, 2.0]},
    }
    assert map_live_frame(_frame("full", payload), mode="basic") is None


def test_map_script_full_becomes_snapshot_plots_in_full_mode():
    payload = {
        "seriesKey": KEY_TEXT,
        "count": 2,
        "closed_upto": 0,
        "plots": [[1.0, 2.0]],
        "series": {"a": [1.0, 2.0]},
    }
    out = map_live_frame(_frame("full", payload), mode="full")
    assert isinstance(out, bytes)
    assert out[:4] == b"AXB1"
    assert out[5] == int(axb1.Axb1Opcode.SNAPSHOT_PLOTS)


def test_map_delta_multi_bar_becomes_append_bars_in_full_mode():
    delta = make_delta("sess-7f3a", 7, 8, 10, 2, LAST_TIME, "sub-1", bars=BARS[-2:])
    out = map_live_frame(delta, last_time=LAST_TIME, mode="full")
    assert isinstance(out, bytes)
    assert out[:4] == b"AXB1"
    assert out[5] == int(axb1.Axb1Opcode.APPEND_BARS)


def test_map_script_delta_becomes_plot_tip_in_full_mode():
    payload = {
        "base_index": 10,
        "count": 11,
        "tail_len": 1,
        "closed_upto": LAST_TIME,
        "forming": True,
        "series": {"myPlot": [1.5]},
    }
    out = map_live_frame(_frame("delta", payload), mode="full")
    assert isinstance(out, bytes)
    assert out[:4] == b"AXB1"
    assert out[5] == int(axb1.Axb1Opcode.PLOT_TIP)


def test_map_full_with_leftovers_stays_json():
    payload = {"seriesKey": KEY_TEXT, "count": 1, "closed_upto": 0, "bars": BARS[:1], "meta": {"x": 1}}
    assert map_live_frame(_frame("full", payload)) is None


def test_map_full_with_count_mismatch_stays_json():
    payload = {"seriesKey": KEY_TEXT, "count": 3, "closed_upto": 0, "bars": BARS[:1]}
    assert map_live_frame(_frame("full", payload)) is None


def _retick_delta(bar_time: int = LAST_TIME) -> dict:
    # Hub frames carry the subscription id the client subscribed with
    # (production: the series key string; here "sub-1"), not the series key.
    return make_delta(
        "sess-7f3a",
        5,
        9,
        10,
        1,
        bar_time,
        "sub-1",
        forming=True,
        bars=[dict(BARS[-1], time=bar_time, volume=2.0)],
    )


def _append_delta() -> dict:
    return make_delta(
        "sess-7f3a",
        6,
        10,
        11,
        1,
        LAST_TIME,
        "sub-1",
        forming=True,
        bars=[dict(BARS[-1], time=LAST_TIME + 60, volume=2.0)],
    )


def test_map_delta_re_tick_becomes_tip():
    out = map_live_frame(_retick_delta(), last_time=LAST_TIME)
    assert isinstance(out, bytes)
    assert out[5] == int(axb1.Axb1Opcode.TIP_UPDATE)


def test_map_delta_append_stays_json():
    # An append is byte-identical to a re-tick in base_index/count/tail_len;
    # only the cursor (bar.time > last_time) can tell them apart.
    assert map_live_frame(_append_delta(), last_time=LAST_TIME) is None


def test_map_delta_re_tick_without_cursor_stays_json():
    assert map_live_frame(_retick_delta(), last_time=None) is None


def test_map_delta_multi_bar_stays_json():
    delta = make_delta("sess-7f3a", 7, 8, 10, 2, LAST_TIME, SUB_ID, bars=BARS[-2:])
    assert map_live_frame(delta, last_time=LAST_TIME) is None


def test_map_delta_unchanged_becomes_unchanged():
    payload = {"base_index": 10, "count": 10, "tail_len": 0, "closed_upto": LAST_TIME, "unchanged": True}
    out = map_live_frame(_frame("delta", payload), last_time=LAST_TIME)
    assert isinstance(out, bytes)
    assert out[5] == int(axb1.Axb1Opcode.UNCHANGED)


def test_map_delta_unchanged_with_bars_stays_json():
    payload = {
        "base_index": 9,
        "count": 10,
        "tail_len": 1,
        "closed_upto": LAST_TIME,
        "unchanged": True,
        "bars": BARS[-1:],
    }
    assert map_live_frame(_frame("delta", payload), last_time=LAST_TIME) is None


def test_map_close_becomes_close_verify():
    close = make_close("sess-7f3a", 7, 9, LAST_TIME, BARS[-1], SUB_ID)
    out = map_live_frame(close, last_time=LAST_TIME)
    assert isinstance(out, bytes)
    assert out[5] == int(axb1.Axb1Opcode.CLOSE_VERIFY)


def test_map_close_with_tip_becomes_append_bar():
    close = make_close("sess-7f3a", 8, 9, LAST_TIME, BARS[-1], SUB_ID)
    close["payload"]["tip"] = {"time": LAST_TIME + 60, "close": 1.5, "volume": 2.0}
    out = map_live_frame(close, last_time=LAST_TIME)
    assert isinstance(out, bytes)
    assert out[5] == int(axb1.Axb1Opcode.APPEND_BAR)


def test_map_error_becomes_binary_error():
    frame = {"type": "error", "id": SUB_ID, "code": "REPAIR", "message": "gap at seq 4", "retryable": True}
    out = map_live_frame(frame)
    assert isinstance(out, bytes)
    assert out[5] == int(axb1.Axb1Opcode.ERROR)


def test_map_control_frames_stay_json():
    assert map_live_frame({"type": "pong", "id": SUB_ID}) is None
    assert map_live_frame({"type": "auth.ok"}) is None


def test_map_frames_without_id_stay_json():
    assert map_live_frame({"type": "status", "sessionId": "s", "seq": 1, "payload": {"code": "live"}}) is None


# -- LiveConnection negotiation (socket-free, fake sender + fake hub) ------


class _CaptureSender:
    """Records exactly what ``serve_live_ws`` would put on the socket."""

    def __init__(self):
        self.frames: list = []

    def __call__(self, frame):
        self.frames.append(frame)


class _FakeHub:
    """PushHub stand-in that records the connection's registered callback."""

    def __init__(self):
        self.registered: dict = {}

    def register(self, client_id, send):
        self.registered[client_id] = send

    def unregister(self, client_id):
        self.registered.pop(client_id, None)


def _axb1_conn(sender, **kw):
    def _ensurer(_kind, _key, _history, **_kw):
        return {"outcome": "ready", "session_id": None, "count": 10, "newest": 1}

    return LiveConnection(
        registry=LiveRegistry(),
        authed=True,
        ensurer=_ensurer,
        store_window=lambda _key, _limit: BARS,
        attacher=lambda *_a, **_k: None,
        sender=sender,
        **kw,
    )


def _subscribe(encoding=None) -> dict:
    payload: dict = {"kind": "series", "meta": META}
    if encoding is not None:
        payload["encoding"] = encoding
    return {"type": "subscribe", "id": "sub-1", "payload": payload}


def test_subscribe_with_axb1_sends_bytes():
    capture = _CaptureSender()
    conn = _axb1_conn(capture)
    replies = conn.handle_dict(_subscribe("axb1"))
    # The early datafeed-loading status went through the negotiated wire.
    assert len(capture.frames) == 1
    assert isinstance(capture.frames[0], bytes)
    assert capture.frames[0][:4] == b"AXB1"
    assert capture.frames[0][5] == int(axb1.Axb1Opcode.STATUS)
    wire = [conn.encode_outbound(reply) for reply in replies]
    assert [f[5] for f in wire] == [
        int(axb1.Axb1Opcode.STATUS),
        int(axb1.Axb1Opcode.SNAPSHOT_OHLCV),
        int(axb1.Axb1Opcode.STATUS),
    ]


def test_subscribe_axb1_full_sends_binary_for_status_and_snapshot():
    capture = _CaptureSender()
    hub = _FakeHub()
    conn = _axb1_conn(capture, hub=hub)
    replies = conn.handle_dict(_subscribe("axb1-full"))
    assert len(capture.frames) == 1
    assert isinstance(capture.frames[0], bytes)
    assert capture.frames[0][5] == int(axb1.Axb1Opcode.STATUS)
    wire = [conn.encode_outbound(reply) for reply in replies]
    assert [f[5] for f in wire] == [
        int(axb1.Axb1Opcode.STATUS),
        int(axb1.Axb1Opcode.SNAPSHOT_OHLCV),
        int(axb1.Axb1Opcode.STATUS),
    ]
    send = hub.registered["sub-1"]
    send(
        make_delta(
            "sess-7f3a",
            12,
            10,
            11,
            1,
            LAST_TIME,
            "sub-1",
            forming=True,
            series={"myPlot": [1.5]},
        )
    )
    assert isinstance(capture.frames[-1], bytes)
    assert capture.frames[-1][5] == int(axb1.Axb1Opcode.PLOT_TIP)


def test_without_encoding_flag_everything_stays_json():
    capture = _CaptureSender()
    conn = _axb1_conn(capture)
    replies = conn.handle_dict(_subscribe())
    assert isinstance(capture.frames[0], dict)
    assert capture.frames[0]["payload"]["code"] == "datafeed-loading"
    wire = [conn.encode_outbound(reply) for reply in replies]
    assert all(isinstance(frame, dict) for frame in wire)
    assert wire[1]["type"] == "full"


def test_hub_delta_re_tick_leaves_as_tip():
    capture = _CaptureSender()
    hub = _FakeHub()
    conn = _axb1_conn(capture, hub=hub)
    replies = conn.handle_dict(_subscribe("axb1"))
    # serve_live_ws.dispatch pipes every reply through encode_outbound; the
    # `full` snapshot is what seeds the cursor that classifies re-ticks.
    for reply in replies:
        conn.encode_outbound(reply)
    send = hub.registered["sub-1"]
    send(_retick_delta())
    assert isinstance(capture.frames[-1], bytes)
    assert capture.frames[-1][5] == int(axb1.Axb1Opcode.TIP_UPDATE)


def test_hub_delta_append_stays_json():
    capture = _CaptureSender()
    hub = _FakeHub()
    conn = _axb1_conn(capture, hub=hub)
    conn.handle_dict(_subscribe("axb1"))
    send = hub.registered["sub-1"]
    send(_append_delta())
    assert isinstance(capture.frames[-1], dict)
    assert capture.frames[-1]["type"] == "delta"


def test_hub_delta_multi_bar_stays_json():
    capture = _CaptureSender()
    hub = _FakeHub()
    conn = _axb1_conn(capture, hub=hub)
    conn.handle_dict(_subscribe("axb1"))
    send = hub.registered["sub-1"]
    send(make_delta("sess-7f3a", 9, 8, 10, 2, LAST_TIME, "sub-1", bars=BARS[-2:]))
    assert isinstance(capture.frames[-1], dict)


def test_close_replies_leave_as_close_verify():
    capture = _CaptureSender()
    conn = _axb1_conn(capture)
    conn.handle_dict(_subscribe("axb1"))
    out = conn.encode_outbound(make_close("sess-7f3a", 7, 9, LAST_TIME, BARS[-1], "sub-1"))
    assert isinstance(out, bytes)
    assert out[5] == int(axb1.Axb1Opcode.CLOSE_VERIFY)


def test_error_frames_leave_as_binary_error():
    capture = _CaptureSender()
    conn = _axb1_conn(capture)
    conn.handle_dict(_subscribe("axb1"))
    out = conn.encode_outbound({"type": "error", "id": "sub-1", "code": "X", "message": "boom", "retryable": False})
    assert isinstance(out, bytes)
    assert out[5] == int(axb1.Axb1Opcode.ERROR)


def test_control_and_idle_frames_stay_json_on_wire():
    capture = _CaptureSender()
    conn = _axb1_conn(capture)
    conn.handle_dict(_subscribe("axb1"))
    pong = conn.handle_dict({"type": "ping", "id": "sub-1"})[0]
    assert conn.encode_outbound(pong) == {"type": "pong", "id": "sub-1"}
    idle = make_status("sess-7f3a", "idle", "sub-1")
    assert conn.encode_outbound(idle) is idle


def test_unsubscribe_clears_negotiated_encoding():
    capture = _CaptureSender()
    conn = _axb1_conn(capture)
    conn.handle_dict(_subscribe("axb1"))
    assert isinstance(capture.frames[0], bytes)
    unsub = conn.handle_dict({"type": "unsubscribe", "id": "sub-1"})
    assert unsub[0]["type"] == "status"
    assert unsub[0]["payload"]["code"] == "idle"
    # A fresh subscription on the same id without the flag is plain JSON again.
    conn.handle_dict(_subscribe())
    assert isinstance(capture.frames[-1], dict)


def test_resubscribe_without_encoding_overwrites_state():
    capture = _CaptureSender()
    conn = _axb1_conn(capture)
    conn.handle_dict(_subscribe("axb1"))
    assert isinstance(capture.frames[-1], bytes)
    conn.handle_dict(_subscribe())
    assert isinstance(capture.frames[-1], dict)
