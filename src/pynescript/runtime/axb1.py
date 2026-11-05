# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later

"""AXB1 v1 binary frame encoder — PYNE's side of the cross-repo AXB1 wire contract.

Pure standard library (``struct``); byte-for-byte mirrors the AXIS reference
encoder (``axis/src/hp/axb1/encode.ts`` + ``binary.ts``). The golden vectors in
``tests/data/axb1-vectors.json`` are shared with the AXIS repo
(``axis/tests/hp/axb1-vectors.json``) and asserted by ``tests/test_axb1.py`` —
any layout drift fails both repos' suites instead of silently corrupting live
frames.

Alignment semantics (mirrors ``BinWriter`` in ``binary.ts``):

- ``i64``/``f64`` self-align to 8 before writing; ``i32`` and friends never do.
- ``align(n)`` pads to the next multiple of *n* of the payload-relative offset
  (the 32-byte header is a multiple of 8, so payload-relative == envelope-relative).
- ``pad(n)`` writes *n* zero bytes unconditionally — the tip TIME field's
  trailing ``pad(4)`` is unconditional, not an alignment.
- ``pad_to_4()`` aligns the payload length to 4 — every payload must be a
  multiple of 4 or the envelope is rejected.
"""

from __future__ import annotations

import enum
import math
import struct

from collections.abc import Mapping
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any


AXB1_MAGIC = 0x31425841
AXB1_VERSION = 1
AXB1_HEADER_BYTES = 32
AXB1_MAX_PAYLOAD = 4 * 1024 * 1024

AXB1_HDR_HAS_SUB_ID = 1 << 0
AXB1_HDR_COMPRESSED = 1 << 1

AXB1_STATUS_CODES: tuple[str, ...] = (
    "datafeed-loading",
    "datafeed-ready",
    "calculating",
    "live",
    "degraded",
    "error",
)

PRICE_SCALE_MIN = 0
PRICE_SCALE_MAX = 12
PRICE_SCALE_DEFAULT = 8

MAX_BLOB_FIELD = 0xFFFF
UNKNOWN_STATUS_BYTE = 255


class Axb1Opcode(enum.IntEnum):
    """AXB1 v1 opcodes — exact byte values from the AXIS reference constants."""

    HEARTBEAT = 0x00
    STATUS = 0x01
    SNAPSHOT_OHLCV = 0x02
    SNAPSHOT_PLOTS = 0x03
    TIP_UPDATE = 0x04
    APPEND_BAR = 0x05
    PLOT_TIP = 0x06
    CLOSE_VERIFY = 0x07
    ERROR = 0x08
    UNCHANGED = 0x09
    JSON_BLOB = 0x0A
    APPEND_BARS = 0x0B


class TipMask(enum.IntFlag):
    """Which tip fields a TIP_UPDATE/APPEND_BAR tip carries."""

    OPEN = 1
    HIGH = 2
    LOW = 4
    CLOSE = 8
    VOLUME = 16
    TIME = 32


class ValueKind(enum.IntEnum):
    """SNAPSHOT_PLOTS/PLOT_TIP column kinds."""

    PriceTicks = 0
    UnitFloat64 = 1


@dataclass(frozen=True, slots=True)
class Header:
    """AXB1 envelope header (32 bytes, little-endian)."""

    seq: int = 0
    sub_id_hash: int = 0
    session_hash: int = 0
    ts_ms: int = 0
    hdr_flags: int = 0


class _Writer:
    """Little-endian payload writer with ``BinWriter`` alignment semantics."""

    def __init__(self) -> None:
        self._buf = bytearray()

    def pad(self, n: int) -> None:
        if n > 0:
            self._buf.extend(b"\x00" * n)

    def align(self, n: int) -> None:
        remainder = len(self._buf) % n
        if remainder:
            self.pad(n - remainder)

    def u8(self, v: int) -> None:
        self._buf.append(v & 0xFF)

    def u16(self, v: int) -> None:
        self._buf.extend(struct.pack("<H", v & 0xFFFF))

    def u32(self, v: int) -> None:
        self._buf.extend(struct.pack("<I", v & 0xFFFFFFFF))

    def i32(self, v: int) -> None:
        self._buf.extend(struct.pack("<i", v))

    def i64(self, v: int) -> None:
        self.align(8)
        self._buf.extend(struct.pack("<q", v))

    def f64(self, v: float) -> None:
        self.align(8)
        self._buf.extend(struct.pack("<d", v))

    def raw(self, data: bytes) -> None:
        self._buf.extend(data)

    def pad_to_4(self) -> None:
        self.align(4)

    def finish(self) -> bytes:
        return bytes(self._buf)


def fnv1a32(text: str) -> int:
    """FNV-1a 32 of the UTF-8 bytes; ``""`` hashes to the offset basis.

    Used to turn subscription ids / session ids into the header's
    ``sub_id_hash`` / ``session_hash`` — the AXIS ingest side mirrors this to
    route frames back to the right subscription.
    """
    acc = 2166136261
    for byte in text.encode("utf-8"):
        acc ^= byte
        acc = (acc * 16777619) & 0xFFFFFFFF
    return acc


def assert_price_scale(scale: int) -> int:
    """Validate the price scale (whole number in ``PRICE_SCALE_MIN..MAX``)."""
    if isinstance(scale, bool) or not isinstance(scale, int):
        detail = "price_scale must be an integer"
        raise ValueError(detail)
    if not PRICE_SCALE_MIN <= scale <= PRICE_SCALE_MAX:
        detail = f"price_scale must be within {PRICE_SCALE_MIN}..{PRICE_SCALE_MAX}"
        raise ValueError(detail)
    return scale


def price_to_ticks(price: float, scale: int = PRICE_SCALE_DEFAULT) -> int:
    """Canonical price ticks: JS ``Math.round(price * 10**scale)`` semantics.

    Python's ``round()`` is banker's rounding and would diverge on exact
    halves, so the JS half-toward-+Inf rule is spelled out as ``floor(x + 0.5)``
    (equivalent to ``Math.round`` for the finite magnitudes on this wire).
    """
    assert_price_scale(scale)
    value = float(price)
    if not math.isfinite(value):
        detail = "price must be finite"
        raise ValueError(detail)
    return math.floor(value * (10**scale) + 0.5)


def encode_envelope(header: Header, payload: bytes) -> bytes:
    """Wrap a 4-aligned payload in the 32-byte AXB1 header (opcode byte left 0)."""
    flags = int(header.hdr_flags)
    if flags & AXB1_HDR_COMPRESSED:
        detail = "AXB1 v1 forbids compressed payloads"
        raise ValueError(detail)
    if len(payload) & 3:
        detail = "payload_bytes must be a multiple of 4"
        raise ValueError(detail)
    if len(payload) > AXB1_MAX_PAYLOAD:
        detail = "payload_bytes exceeds AXB1_MAX_PAYLOAD"
        raise ValueError(detail)
    out = bytearray(AXB1_HEADER_BYTES + len(payload))
    struct.pack_into("<I", out, 0, AXB1_MAGIC)
    out[4] = AXB1_VERSION
    out[5] = 0  # opcode — set by _wrap once the payload is finalized
    struct.pack_into("<H", out, 6, flags & 0xFFFF)
    struct.pack_into("<I", out, 8, header.sub_id_hash & 0xFFFFFFFF)
    struct.pack_into("<I", out, 12, header.seq & 0xFFFFFFFF)
    struct.pack_into("<I", out, 16, header.session_hash & 0xFFFFFFFF)
    struct.pack_into("<I", out, 20, len(payload))
    struct.pack_into("<Q", out, 24, int(header.ts_ms) & 0xFFFFFFFFFFFFFFFF)
    out[AXB1_HEADER_BYTES:] = payload
    return bytes(out)


def _wrap(opcode: Axb1Opcode, header: Header, payload: bytes) -> bytes:
    envelope = bytearray(encode_envelope(header, payload))
    envelope[5] = int(opcode)
    return bytes(envelope)


def encode_heartbeat(header: Header) -> bytes:
    """Empty-payload HEARTBEAT."""
    return _wrap(Axb1Opcode.HEARTBEAT, header, b"")


def encode_unchanged(header: Header) -> bytes:
    """Empty-payload UNCHANGED (cursor/count derived by the client from its own)."""
    return _wrap(Axb1Opcode.UNCHANGED, header, b"")


def encode_status(header: Header, *, status_code: str, detail: str, have: int, need: int) -> bytes:
    """STATUS: ``u8 idx, u8 0, u16 detail_len, detail, align4, u32 have, u32 need, pad4``."""
    w = _Writer()
    try:
        code_index: int | None = AXB1_STATUS_CODES.index(status_code)
    except ValueError:
        code_index = None
    detail_bytes = str(detail).encode("utf-8")
    if len(detail_bytes) > MAX_BLOB_FIELD:
        detail = "status detail too long"
        raise ValueError(detail)
    w.u8(UNKNOWN_STATUS_BYTE if code_index is None else code_index)
    w.u8(0)
    w.u16(len(detail_bytes))
    w.raw(detail_bytes)
    w.align(4)
    w.u32(have)
    w.u32(need)
    w.pad_to_4()
    return _wrap(Axb1Opcode.STATUS, header, w.finish())


def _write_ohlcv(w: _Writer, ohlcv: Mapping[str, Any], count: int) -> None:
    """Columnar OHLCV: i64 prices (ticks, self-align-8) then f64 volume."""
    for name in ("open", "high", "low", "close"):
        column = ohlcv[name]
        if len(column) != count:
            detail = "SNAPSHOT_OHLCV column length mismatch"
            raise ValueError(detail)
    volumes = ohlcv["volume"]
    if len(volumes) != count:
        detail = "SNAPSHOT_OHLCV column length mismatch"
        raise ValueError(detail)
    for name in ("open", "high", "low", "close"):
        for value in ohlcv[name]:
            w.i64(int(value))
    for value in volumes:
        w.f64(float(value))


def encode_snapshot_ohlcv(
    header: Header,
    *,
    price_scale: int,
    count: int,
    closed_upto: int,
    hot_from_index: int,
    time_s: Sequence[int],
    flags: Sequence[int],
    ohlcv: Mapping[str, Sequence[Any]],
) -> bytes:
    """SNAPSHOT_OHLCV: meta + time column (align 8) + columnar OHLCV + u8 flags."""
    assert_price_scale(price_scale)
    if len(time_s) != count or len(flags) != count:
        detail = "SNAPSHOT_OHLCV column length mismatch"
        raise ValueError(detail)
    w = _Writer()
    w.u8(price_scale)
    w.pad(3)
    w.u32(count)
    w.u32(closed_upto)
    w.u32(hot_from_index)
    for value in time_s:
        w.i32(int(value))
    w.align(8)
    _write_ohlcv(w, ohlcv, count)
    for value in flags:
        w.u8(int(value))
    w.pad_to_4()
    return _wrap(Axb1Opcode.SNAPSHOT_OHLCV, header, w.finish())


def _write_plots(w: _Writer, plots: Sequence[Mapping[str, Any]], count: int) -> None:
    """Plot column: ``u8 kind, u8 0, u16 keylen, key, align8, values…``."""
    for column in plots:
        kind = ValueKind(column["kind"])
        key = column.get("key")
        if key is None:
            detail = "plot key missing"
            raise ValueError(detail)
        raw_key = str(key).encode("utf-8")
        if len(raw_key) > MAX_BLOB_FIELD:
            detail = "plot key too long"
            raise ValueError(detail)
        w.u8(int(kind))
        w.u8(0)
        w.u16(len(raw_key))
        w.raw(raw_key)
        w.align(8)
        if kind is ValueKind.PriceTicks:
            values = column.get("ticks")
            if values is None or len(values) != count:
                detail = "plot ticks length mismatch"
                raise ValueError(detail)
            for value in values:
                w.i64(int(value))
        else:
            values = column.get("values")
            if values is None or len(values) != count:
                detail = "plot values length mismatch"
                raise ValueError(detail)
            for value in values:
                w.f64(float(value))


def encode_snapshot_plots(
    header: Header,
    *,
    count: int,
    closed_upto: int,
    times: Sequence[int] | None,
    plots: Sequence[Mapping[str, Any]],
) -> bytes:
    """SNAPSHOT_PLOTS: meta + optional time column + plot columns."""
    w = _Writer()
    w.u32(count)
    w.u32(closed_upto)
    w.u32(len(plots))
    w.u32(1 if times is not None else 0)
    if times is not None:
        if len(times) != count:
            detail = "SNAPSHOT_PLOTS times length mismatch"
            raise ValueError(detail)
        for value in times:
            w.i32(int(value))
        w.align(8)
    _write_plots(w, plots, count)
    return _wrap(Axb1Opcode.SNAPSHOT_PLOTS, header, w.finish())


def _write_tip(w: _Writer, tip: Mapping[str, Any], *, require_time: bool) -> None:
    """Tip: ``u32 mask, u32 flags`` then masked fields in OPEN→…→TIME order."""
    mask = int(tip.get("mask", 0))
    if require_time and not mask & TipMask.TIME:
        detail = "TIP_UPDATE tip requires TIME"
        raise ValueError(detail)
    w.u32(mask)
    w.u32(int(tip.get("flags", 0)))
    for name, bit in (("open", TipMask.OPEN), ("high", TipMask.HIGH), ("low", TipMask.LOW), ("close", TipMask.CLOSE)):
        if mask & bit:
            value = tip.get(name)
            if value is None:
                detail = f"TIP {name} missing"
                raise ValueError(detail)
            w.i64(int(value))
    if mask & TipMask.VOLUME:
        value = tip.get("volume")
        if value is None or not math.isfinite(float(value)):
            detail = "TIP volume missing"
            raise ValueError(detail)
        w.f64(float(value))
    if mask & TipMask.TIME:
        value = tip.get("time_s")
        if value is None:
            detail = "TIP time missing"
            raise ValueError(detail)
        w.i32(int(value))
        w.pad(4)


def encode_tip_update(header: Header, tip: Mapping[str, Any]) -> bytes:
    """TIP_UPDATE: forming-bar re-tick (TIME required — the tip is always bar-scoped)."""
    w = _Writer()
    _write_tip(w, tip, require_time=True)
    w.pad_to_4()
    return _wrap(Axb1Opcode.TIP_UPDATE, header, w.finish())


def _write_bar_ohlcv(w: _Writer, ohlcv: Mapping[str, Any]) -> None:
    """One bar's OHLCV as **scalar** ticks/volume (CLOSE_VERIFY / APPEND_BAR).

    Mirrors the TS frames where ``open``…``close`` are single ``bigint``s;
    the columnar :func:`_write_ohlcv` is for ``SNAPSHOT_OHLCV`` only.
    """
    for name in ("open", "high", "low", "close"):
        if name not in ohlcv:
            detail = f"bar ohlcv is missing {name}"
            raise ValueError(detail)
    if "volume" not in ohlcv:
        detail = "bar ohlcv is missing volume"
        raise ValueError(detail)
    for name in ("open", "high", "low", "close"):
        w.i64(int(ohlcv[name]))
    w.f64(float(ohlcv["volume"]))


def encode_append_bar(
    header: Header,
    *,
    price_scale: int,
    closed_index: int,
    closed_time: int,
    ohlcv: Mapping[str, Any],
    tip: Mapping[str, Any],
) -> bytes:
    """APPEND_BAR: closed-bar confirmation + the next forming tip."""
    assert_price_scale(price_scale)
    w = _Writer()
    w.u8(price_scale)
    w.pad(3)
    w.u32(closed_index)
    w.i32(closed_time)
    w.pad(4)
    _write_bar_ohlcv(w, ohlcv)
    _write_tip(w, tip, require_time=False)
    w.pad_to_4()
    return _wrap(Axb1Opcode.APPEND_BAR, header, w.finish())


def encode_append_bars(
    header: Header,
    *,
    price_scale: int,
    count: int,
    closed_upto: int,
    closed_index: int,
    time_s: Sequence[int],
    flags: Sequence[int],
    ohlcv: Mapping[str, Sequence[Any]],
    tip: Mapping[str, Any],
) -> bytes:
    """APPEND_BARS: a batch of newly closed bars + an optional forming tip.

    Mirrors :func:`encode_snapshot_ohlcv` columnar layout, prefixed by the
    batch cursor (closed_upto / closed_index) and an ``has_tip`` flag.
    """
    assert_price_scale(price_scale)
    if len(time_s) != count or len(flags) != count:
        detail = "APPEND_BARS column length mismatch"
        raise ValueError(detail)
    for name in ("open", "high", "low", "close", "volume"):
        if len(ohlcv[name]) != count:
            detail = "APPEND_BARS column length mismatch"
            raise ValueError(detail)
    has_tip = bool(int(tip.get("mask", 0)) & TipMask.TIME)
    w = _Writer()
    w.u8(price_scale)
    w.pad(3)
    w.u32(count)
    w.u32(closed_upto)
    w.u32(closed_index)
    w.u32(1 if has_tip else 0)
    for value in time_s:
        w.i32(int(value))
    w.align(8)
    _write_ohlcv(w, ohlcv, count)
    for value in flags:
        w.u8(int(value))
    w.pad_to_4()
    if has_tip:
        _write_tip(w, tip, require_time=False)
    w.pad_to_4()
    return _wrap(Axb1Opcode.APPEND_BARS, header, w.finish())


def encode_plot_tip(header: Header, plots: Sequence[Mapping[str, Any]]) -> bytes:
    """PLOT_TIP: ``u32 len, u32 0`` then ``u32 key_hash, u8 kind, pad3, value…``."""
    w = _Writer()
    w.u32(len(plots))
    w.u32(0)
    for column in plots:
        w.u32(int(column["key_hash"]))
        kind = ValueKind(column["kind"])
        w.u8(int(kind))
        w.pad(3)
        if kind is ValueKind.PriceTicks:
            ticks = column.get("ticks")
            if ticks is None:
                detail = "PLOT_TIP ticks missing"
                raise ValueError(detail)
            w.i64(int(ticks))
        else:
            value = column.get("value")
            if value is None or not math.isfinite(float(value)):
                detail = "PLOT_TIP value missing"
                raise ValueError(detail)
            w.f64(float(value))
    w.pad_to_4()
    return _wrap(Axb1Opcode.PLOT_TIP, header, w.finish())


def encode_close_verify(header: Header, *, index: int, time_s: int, ohlcv: Mapping[str, Any]) -> bytes:
    """CLOSE_VERIFY: bar identity (index + time) + the closed bar's final OHLCV.

    No explicit pad after the ``i32`` time: the first OHLCV ``i64`` self-aligns
    to 8, and payload offset 8 is already aligned — mirroring ``encode.ts``
    (48-byte payload, envelope length ``0x30``).
    """
    w = _Writer()
    w.u32(index)
    w.i32(time_s)
    _write_bar_ohlcv(w, ohlcv)
    w.pad_to_4()
    return _wrap(Axb1Opcode.CLOSE_VERIFY, header, w.finish())


def encode_error(header: Header, *, code: str, message: str, retryable: bool) -> bytes:
    """ERROR: ``u16 code_len, u16 msg_len, u8 retryable, pad3, code, message, pad4``."""
    w = _Writer()
    code_bytes = str(code).encode("utf-8")
    message_bytes = str(message).encode("utf-8")
    if len(code_bytes) > MAX_BLOB_FIELD:
        detail = "error code too long"
        raise ValueError(detail)
    if len(message_bytes) > MAX_BLOB_FIELD:
        detail = "error message too long"
        raise ValueError(detail)
    w.u16(len(code_bytes))
    w.u16(len(message_bytes))
    w.u8(1 if retryable else 0)
    w.pad(3)
    w.raw(code_bytes)
    w.raw(message_bytes)
    w.pad_to_4()
    return _wrap(Axb1Opcode.ERROR, header, w.finish())


def encode_json_blob(header: Header, json_text: str) -> bytes:
    """JSON_BLOB: ``u32 len`` + UTF-8 JSON (leftovers / drawings / anything unmapped)."""
    w = _Writer()
    raw_json = str(json_text).encode("utf-8")
    if len(raw_json) > AXB1_MAX_PAYLOAD:
        detail = "JSON_BLOB too large"
        raise ValueError(detail)
    w.u32(len(raw_json))
    w.raw(raw_json)
    w.pad_to_4()
    return _wrap(Axb1Opcode.JSON_BLOB, header, w.finish())
