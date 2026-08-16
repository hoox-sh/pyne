# Copyright (C) 2024-2026 jango_blockchained
#
# SPDX-License-Identifier: AGPL-3.0-or-later

# AGENT 06 — Trail-on-OHLC dual-host goldens

| Field | Value |
| --- | --- |
| **Role / ID** | Agent 06 — Partial trail-on-OHLC |
| **Verdict** | **closed** |
| **Date** | 2026-08-16 |

OHLC `strategy.exit(..., trail_offset=...)` is locked interpret ≡ compile on
synthetic bars (same position path, fill prices, placement events). Tick-path
trail remains out of scope.

## What you did (files touched)

| File | Change |
| --- | --- |
| `src/pynescript/compiler/strategy_broker.py` | Exit placement: visitor `comment=` (Pine `strategy.exit` id) is the order name when `id` is omitted — pending keys + `kind=exit` events match interpret (`XT` not `exit` / `id=None`) |
| `tests/test_trail_ohlc_dual_host.py` | **New** Runtime dual-host goldens (7 cases) |
| `docs/gaps_close_2026-08-16/AGENT_06_trail_ohlc.md` | This report |

Did **not** edit interpret `strategy.py` (no trail-math bug). Did **not** invent
tick simulation. Did **not** touch nvi, supertrend, plot keys, Flask, pynets,
or `request.*`. Left `tests/test_order_fills.py` unit goldens as-is (new file
is the cleaner Runtime home).

## Root causes / findings

1. **Trail OHLC math already matched**  
   Both hosts ratchet `stop = high − offset` (long) / `low + offset` (short)
   in `process_pending_orders` / compile `PendingOrder`. Probe fills were
   already `$109` long / `$91` short before the broker tweak.

2. **Compile exit id was dropped**  
   Compiler maps `strategy.exit("XT", …)` → `__strategy.close(comment="XT", …)`.
   `close()` used `id=None` → pending base `"exit"` and placement `id=None`.
   Broker now treats omitted `id` + non-empty `comment` as the exit order name.

3. **Interpret Runtime drops start-of-bar fill events**  
   Host clears the strategy event buffer after `process_pending_orders` and
   before `visit()`. Next-bar trail fills therefore omit interpret `order` /
   `close` events. Compile keeps them. Fill prices are still visible on both
   via `strategy.closedtrades.exit_price`. Same-bar place+fill (inside
   `visit` / `close`) keeps the `order` fill on both hosts.

## Goldens locked (`tests/test_trail_ohlc_dual_host.py`)

Default Runtime `mintick=0.01` → `trail_offset=100` is `$1`.

| Case | Bars | Locked |
| --- | --- | --- |
| Long ratchet | high 110 → stop 109; pullback holds; low 108 fills | `ps`/`ct`/`xp=109`/`pnl=18`; entry `L` + exit `XT` |
| Short ratchet | low 90 → stop 91; bounce holds; high 92 fills | `xp=91`; `ps` −2→0 |
| Same-bar fill | place + high 110 / low 108 on one bar | `xp=109`; both emit `order` id=`XT` stop=109 |
| `trail_price=110` + offset 200 | arm at high 112 (stop 110); fill 110 | `xp=110`; exit stop=110 |
| `trail_points` wins | points=100 beats offset=500 | `xp=109` (not 105) |
| `trail_points=0` fallback | offset=100 still trails | `xp=109` (not market-close) |
| `from_entry="A"` | pyramided A+B; trail closes A only | `ps` 6→4; `xp=109`; `ot` 2→1 |

## Tests run

```bash
PYTHONPATH=src:. .venv/bin/python -m pytest \
  tests/test_order_fills.py \
  tests/test_compiler_strategy.py \
  tests/test_strategy_events.py \
  tests/test_trail_ohlc_dual_host.py \
  -q --tb=short
# 128 passed
```

## Residual / out of scope

- **Tick-path trail** — still OHLC-approx (bar high/low only). Same residual
  as `docs/known_divergences.md` Strategy / Trail stops.
- **Interpret Runtime fill-event drain** — next-bar `order`/`close` fills are
  compile-only in `Runtime.run` output. Placement events + `exit_price` series
  are the dual-host contract.
- Compile fill envelope still emits an extra `kind=close` (from
  `_apply_fill` → `close(price=…)`) plus `order` `fill:XT`; interpret same-bar
  fill is `order` `comment="fill"` only. Not a fill-price divergence.

## Verdict

**closed** — Partial trail-on-OHLC is locked dual-host on the OHLC model.
Tick-path trail is explicitly not this close.
