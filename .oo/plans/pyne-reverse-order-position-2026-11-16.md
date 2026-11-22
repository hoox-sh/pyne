# Pre-placed opposite `strategy.order`: net position semantics (compile fix)

**Date:** 2026-11-16
**Card:** `pyne-reverse-order-position-sema-aa6b29e7`
**Status:** Landed — operator-approved commit/push (2026-11-16)

## Why

Same-bar probe: long limit 95 + short `strategy.order` limit 105 both fill on
bar high 106 / low 94. The hosts diverged on the resulting position:

| Shape (long, sell) | Reference net | Interpret | Compile before |
| --- | --- | --- | --- |
| 2, 1 | long 1 | long 1 | short 1 |
| 1, 1 | flat | flat | short 1 |
| 1, 2 | short 1 | short 1 | short 2 |

Reference Pine (`strategy.order`): "the resulting market position is the
*net sum* of the open position size and the filled order quantity"; "the
`strategy.order()` command *does not* automatically reverse open positions."
Only `strategy.entry()` reverses (close the whole opposite position, then open
the entry qty). Source: TradingView Pine v6 docs, Strategies → Order placement
→ `strategy.order()` / Reversing positions.

**Choice:** compile is the questionable host. Interpret already matches the
net-sum spec on all three shapes, so this slice fixes compile rather than
making interpret copy the over-reverse.

## Change

- `CompileStrategyBroker.order`: `is_entry=False` always. A raw order is never
  an entry-target order; the flag was latched from the placement-time position,
  which is why a pre-placed sell became an entry-style reverse at fill time.
- `_apply_fill` non-entry opposite branch: cover `min(fill_qty, open size)`,
  then open the remainder (`leftover`). Previously it passed `fill_qty` to
  `close` and dropped any excess beyond the open size.
- Risk gate restored for raw orders: non-covering opens (flat / same-direction)
  are gated before any qty is consumed, and an opposite fill's leftover is
  gated after the cover. Pure covers stay ungated. `risk_blocked` is emitted
  and the order popped exactly like interpret.

`strategy.entry` target-position semantics are unchanged.

## Acceptance criteria

1. Long 2, pre-placed sell 1 → position `+1` (long 1) on interpret and compile.
2. Long 1, pre-placed sell 1 → position `0` (flat) on both.
3. Long 1, pre-placed sell 2 → position `-1` (short 1) on both.
4. Each shape closes exactly one trade of size 1 (`ct=1`, `cs=1`).
5. `allow_entry_in(long)`: a flat raw short order is blocked (`ps=0`,
   `risk_blocked`) on both hosts.
6. `allow_entry_in(long)`: long 1 + sell 2 covers 1 ungated, blocks the short
   leftover (`ps=0`, `ct=1`, `risk_blocked`) on both hosts.
7. Pure cover (long 1 + sell 1) stays ungated (`ps=0`, no `risk_blocked`).
8. Existing MAE/MFE parity (including the same-bar closed-leg 22/2 partial)
   stays green.
9. Targeted suites green; named token asserted.

## Failing before

- `pyne-reverse-order-position-2026-11-16.failing-before.txt` — 3 failed:
  compile `-1 / -1 / -2` vs spec `+1 / 0 / -1`; interpret passed.
- `pyne-reverse-order-position-2026-11-16.failing-before-risk.txt` — 2 failed:
  compile opened the flat short and the leftover short (`ps=-1`) despite
  `allow_entry_in(long)`; pure cover passed.

## Results

- `tests/test_reverse_order_semantics.py` — **6 passed** (3 net + 3 risk).
- `tests/test_mae_realtime_ticks.py` — **17 passed** (same-bar closed-leg
  parity preserved).
- Targeted realtime/strategy suite + new file — **229 passed**.
- Proof token:
  `REVERSE_ORDER_OK reduce=1.0 flat=0.0 excess=-1.0 closed=1.0 risk_flat=0.0 risk_leftover=0.0 cover=1`.

## Proof

Card `pyne-reverse-order-position-sema-aa6b29e7` (HQ board), attached from the
workspace root with `OO_SEAT=oo-spec-2`:

| Proof | Id | Assertion |
| --- | --- | --- |
| named risk gate | `ed6f538b-2862-4940-8786-9c8b65be5058` | `raw_order_flat_open_blocked_by_allow_entry_in` + `raw_order_leftover_blocked_but_cover_allowed` PASSED, 2 passed |
| reverse-order suite | `7fb853a7-e654-422a-bfc8-0f9d2b8eaeed` | 6 passed (3 net + 3 risk) |
| MAE/MFE parity | `274523aa-7114-4db3-a198-da8183f360a6` | 17 passed |
| targeted suite | `ce538c50-6ea0-4e0f-a832-8d4108b4a765` | 229 passed (9 files) |
| `./scripts/verify.sh` | `dcbb53f5-3b01-4e33-8249-1670bfedb7b6` | all passed, 5 passed / 0 skipped |

SHA-256: broker `ab0dd1029100ab85f9257d38f80055566725ab07b9e856804c36f63f43e172a6`,
tests `5b9a10f1ef26fdd951a9fa9d0e53534a0dc9c0906afaa178521670e22af5c47b`,
docs `2b2d792d7a95e2df7d1bed382b9d4841c4d555e245fe4167b39f3f0c714bc72f`,
code+docs patch `3a329339c62fe44bf128f0c480ed2e8cc8e5d128b750610951840a1bc4a40a7a`.
Verify transcript: `.oo/proof/verify-reverse-order-risk-2026-11-16.txt`.

## Files

- `src/pynescript/compiler/strategy_broker.py` — net-order flag, cover/leftover,
  shared non-covering risk gate, leftover risk gate.
- `tests/test_reverse_order_semantics.py` — reduce/full/excess plus flat-open,
  leftover, and pure-cover risk cases on both hosts.
- `docs/known_divergences.md` — F-17 net-order fix + risk-gate note; removed
  the stale trade-queries residual that said the divergence remained, and
  qualified the D-02 `allow_entry_in` wording (policy unchanged; raw-order
  opens now honor it).
- `.oo/plans/pyne-reverse-order-position-2026-11-16.{md,proof.py,failing-before.txt,failing-before-risk.txt}`.

## Residual

- Closed-leg MAE/MFE for a partial close still records the full leg's extremes
  on both hosts (`22/2` for a 2-lot leg), unchanged by this slice.
- `strategy.entry` target-position reverse and the placement/fill gates for
  entries are unchanged; raw-order risk gates now mirror interpret.
- Compile intra-bar pending fills remain deferred (separate card).
