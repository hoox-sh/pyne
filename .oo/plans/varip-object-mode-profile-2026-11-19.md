# Object-mode realtime varip profiling — where the time goes

**Date:** 2026-11-19
**Seat:** oo-spec-2 (deploy) — analysis only, no code changes, no commits
**Question:** Before anyone considers a numeric-path rewrite for realtime `varip`
scripts — is there a realistic >2x win inside object mode itself (caching, fewer copies)?

**Answer (short):** For indicator-style `varip` scripts, object mode realtime overhead
is already tiny (≈ +0.1–0.4 ms per 400-bar run) — no >2x win exists there. For
strategy-style scripts with a realtime window, the object-mode broker snapshot/restore
dominates the delta (~82% of the historical→realtime delta, ~46% of the whole run);
a targeted rollback rewrite (record lengths, truncate on restore, drop per-tick
`dataclasses.replace` of closed trades/events) is worth roughly **1.8–2x on the
strategy realtime path** — but the same broker code serves interpret, and it is a
correctness-sensitive change, not a free lunch. A full numeric rewrite is a dead end
(and is already ruled out on the merits, see §7).

---

## 1. What was measured

Workload: 400 synthetic OHLCV bars, seeded RNG (`random.seed(42)`), 1-minute timestamps.
Realtime window: **last 10 bars re-visited 5× each** (`realtime_bars=10, realtime_ticks=5`)
→ 40 extra bar visits. Historical baseline had no realtime kwargs.

Three representative scripts (sources in §2):

- **A — simple varip counter** (`indicator`, `var int v`, `varip int vip`)
- **B — varip + Pine containers** (`var`/`varip` arrays, `array.push` per bar)
- **C — strategy with varip** (MA-cross, `strategy.entry/close`, `varip int sig`);
  also run as strategy with plain `var` to isolate the varip contribution

Modes:

- `interpret` — AST walker (`Runtime.run(mode="interpret")`)
- `compile` — object mode (all three scripts force object mode: varip ⇒ object mode,
  arrays/UDTs/strategy also force it). Numeric nopython is **not** applicable to varip
  (compiler.py:1397 forces object mode; docs/known_divergences.md records the
  won't-do verdict for numeric varip tick loops).
- `numeric ceiling`: script A with `varip` → `var` (`A_numeric`), compiled in numeric
  nopython, **historical only** — the numeric path cannot express realtime semantics,
  so this is an upper-bound reference, not a candidate.

Harness: `/tmp/varip_bench/bench.py` (wall time, `Runtime.run` host path, warm cache),
`/tmp/varip_bench/probe_breakdown.py` (monkeypatched timers around the snapshot/restore
functions — measurement only, no repo changes), `/tmp/varip_bench/probe_profile.py`
(cProfile, relative attribution only), `/tmp/varip_bench/probe_scale.py`,
`/tmp/varip_bench/recheck*.py` (spot re-verification). Repo was not modified
(`git status`: only the pre-existing `.prettierignore` modification).

Host: linux, CPython 3.14.10, this workspace. Numbers are medians of 7 runs
(9 for the tick sweep); single machine, no CPU pinning.

## 2. Scripts

```pine
// A_simple_varip
//@version=5
indicator("varip counter")
var int v = 0
varip int vip = 0
v := v + 1
vip := vip + 1
plot(v, "v")
plot(vip, "vip")

// B_arrays_varip
//@version=6
indicator("varip containers")
var a = array.new_float()
varip b = array.new_float()
if array.size(a) == 0
    array.push(a, 1.0)
array.push(b, close)
plot(array.size(a), "sa")
plot(array.size(b), "sb")
plot(close)

// C_strategy_varip
//@version=5
strategy("varip ma cross", overlay=true, initial_capital=100000)
fast = ta.sma(close, 10)
slow = ta.sma(close, 30)
varip int sig = 0
if ta.crossover(fast, slow)
    sig := sig + 1
    strategy.entry("L", strategy.long)
if ta.crossunder(fast, slow)
    strategy.close("L")
plot(sig, "sig")
```

`A_numeric` = A with `var int vip`; `A_var`/`B2*` variants in §6.

## 3. Headline numbers (median ms per 400-bar run, warm)

| Script | Mode | Historical | Realtime (10×5) | Δ (RT − hist) |
|---|---|---|---|---|
| A simple varip | interpret | 6.72 | 13.38 (run1 14.35) | **+6.7** (≈2.0×) |
| A simple varip | compile (object) | 1.08 | 1.22 | **+0.14** |
| A simple varip | engine-level (no host packing) | 0.88 | 0.98 | +0.10 |
| A numeric (var, no varip) | numeric nopython | **0.21** | n/a¹ | — |
| B containers | interpret | 11.24 | 18.10 | +6.9 |
| B containers | compile (object) | 1.97 (med 1.89) | 2.28 | **+0.31** |
| C strategy varip | interpret | 19.39 (med 18.84) | 34.22 | **+14.8** |
| C strategy varip | compile (object) | 4.16 | 9.37 | **+5.2** |
| C strategy, `var` instead of `varip` | compile (object)² | 4.11 | 9.58 | +5.5 |

¹ Numeric + active RT window ⇒ host re-emits object mode per call (cached by LRU); measured
≈ 2.0 ms warm — *slower* than compiling the varip script natively in object mode (see §7).
² Strategies force object mode regardless of `varip` — so numeric is off the table for C too.

Tick sweep, A (compile, 10-bar window): ticks=1/3/5 → 1.08 / 1.13 / 1.21 ms (medians) —
no measurable per-tick slope; object-mode rollback is essentially free at this size.
Interpret: 6.78 / 9.70 / 12.76 — **≈150 µs per extra tick (≈40 ticks)**, dominated by
snapshot/restore machinery (§4).

Compile/cached columns (cold → warm, `compile_script(use_cache=False)`, 3 reps):
A object 6.0/1.3 ms · B object 3.3/1.6 ms · C object 4.9/2.1 ms · A numeric numba 459/5.3 ms.
Host first-call vs warm (`Runtime.run` compile path, host cache cleared): 2.8 ms vs 1.1 ms.
The interpret path pays parse+walk on every call; compile mode pays it only on cold cache.

## 4. Where the time goes (attribution)

### 4.1 Interpret mode (RT run, per 400-bar run; monkeypatched timers, 5 reps)

| Component | A (indicator) | C (strategy) |
|---|---|---|
| total (instrumented) | 13.6 ms | 42.0 ms |
| `_snapshot_realtime_scope` | 3.02 ms (40 calls, ~75 µs each) | 3.77 ms |
| `_restore_realtime_scope` | 1.81 ms | 2.41 ms |
| `_snapshot_ta_state` + `_restore_ta_state` | 0.10 ms | 1.64 ms |
| broker `snapshot()` (interpret strategy) | — | 2.35 ms |
| broker `restore()` (interpret strategy) | — | 3.09 ms |
| **rollback total** | **≈4.8 ms (≈36% of run; ≈64% of the hist→RT delta)** | **≈13.3 ms (≈32%; ≈90% of the delta)** |

cProfile (A, RT): `_copy_container_contents` called **5,560× per run = 139 bindings checked per
snapshot** (the evaluator context carries ~all builtins); snapshot+restore chain ≈ 41% of
profiled time. The remaining delta over historical is body re-execution of the 40 extra
visits (~17 µs/bar) plus plot resets.

### 4.2 Object mode (RT run)

Inline `__rt_snap_*` scalar/list copies in the generated bar loop are essentially free at
this size (A: Δ +0.14 ms total). The cost sits in the **strategy broker**:

| Component | C (object mode) |
|---|---|
| run total (host path) | 9.5 ms (engine-level 9.5 ms — host packing ≈ 0) |
| `CompileStrategyBroker.snapshot()` | 1.96 ms (40 calls, ~49 µs each) |
| `CompileStrategyBroker.restore()` | 2.40 ms (40 calls, ~60 µs each) |
| **broker rollback** | **≈4.4 ms — ≈46% of the RT run, ≈82% of the 5.3 ms hist→RT delta** |
| remaining delta (bar body, plot writes, inline snap/restore) | ≈0.9 ms |

cProfile of the generated `execute_script_compiled` (C, RT): 552 `dataclasses._replace`
calls (replace is called per open leg / closed trade record per tick), `snapshot`+`restore`
≈ 10 ms of 19 ms profiled; `begin_bar` ≈ 0.003 s cumulative; host entry ≈ 2 ms.

Root cause, read from `compiler/strategy_broker.py:421-461`: every intermediate tick copies
**all** `events` dicts (`[dict(e) for e in events]`) and `replace()`s **every** open leg,
closed-trade record and pending order — and the compile path **never drains `events`
mid-run** (`to_events()` is called once at the end; contrast with the interpret path, which
drains per confirmed tick at `host.py:2708`). So broker rollback is **O(total events + total
closed trades) per tick**, i.e. O(n²) in trade count across a backtest — it grows with
runtime, not with per-tick state.

### 4.3 varip-vs-var container copies (B-variants, object mode, RT window)

| Variant | hist | RT | Δ |
|---|---|---|---|
| `var acc = array.new_float()` + push every bar (400-elt array at window) | 0.88 | 3.25 | **+2.4 ms** |
| `varip acc = array.new_float()` + push every bar | 0.77 | 0.85 | +0.07 ms |

Rollback copy of a var container is O(size) per intermediate tick — visible and growing
with bar count; varip avoids it entirely. (Array-rollback is required for correctness for
`var`; the issue is that it copies the *whole* array each tick, even if only tail elements
changed — a dirty-flag or copy-on-write scheme would make it incremental.)

### 4.4 Host overhead (both modes, A)

Host first call 2.8 ms vs warm 1.1 ms; engine-level vs host-level delta ≈ 0.2–0.3 ms/run
(JSON packing of series dominates the residual). Numeric-script + active RT window re-emits
object mode per run via `_object_mode_for_realtime()` (cached LRU, not re-transpiled) but
still measured ~0.8 ms/run slower than a native object-mode varip compile — unexplained
residual (see §7), not investigated further.

## 5. Answers to the actual questions

**Is object mode itself slow?** No — for indicators it is 6–11× faster than interpret
(A: 1.22 vs 13.4 ms; C: 9.4 vs 34.2 ms). The RT premium on object mode is small for
indicators (+12%) and moderate for strategies (+125%).

**Can caching/fewer copies inside object mode buy >2x?**
- Indicator varip scripts: **no.** RT cost ≈ 0.14 ms; there is nothing material to remove.
- Strategy RT scripts: **yes, narrowly.** Removing the per-tick full-copy broker rollback
  (truncate `events`/`closed_trade_records` to recorded lengths instead of dict/replace
  copies; keep replace only for genuinely-mutable small structures) would cut ≈4.4 ms of the
  9.5 ms RT run → **≈5 ms, ≈1.9×.** Adding the same treatment on the interpret side
  (scope-binding cache so unchanged bindings aren't re-probed ~139×/tick; interpret broker
  gets the same truncation fix) would cut ≈9–13 ms of the 34–42 ms interpret RT run — but
  interpret is the wrong target while compile exists.
- Analogous O(n)→O(1) fix for var-container tick copies (dirty-tracking) would matter for
  array-heavy scripts (B2: up to +2.4 ms for one 400-elt array).

**Is a numeric-path rewrite the answer? No.** Numeric cannot express varip tick semantics
(hardcoded barstate flags, no tick loop, no rollback constructs — see
`docs/known_divergences.md` "Numeric nopython varip tick loop — won't do", recorded
2026-11-19). The numeric ceiling measured here (0.21 ms historical) is not reachable for
realtime varip at any engineering cost short of a new engine; and object mode already
delivers within ~6× of it while being semantically correct.

## 6. Bottom line / recommendation

1. **Do not green-light a numeric rewrite for varip realtime.** The headroom is ~5× on a
   1 ms base for indicators, and it is not obtainable without re-implementing
   rollback/tick semantics in numba.
2. **If realtime strategy latency matters, fund a broker-rollback optimization** (record
   `len(events)` / `len(closed_trade_records)` / open-leg ids at snapshot; restore by
   truncation + targeted restore; replace `dataclasses.replace` with targeted field restore
   or dirty-flag). Expected: ~1.8–2× on object-mode strategy RT runs (9.5 → ~5 ms here),
   and removes a latent **O(trades × ticks) quadratic** that makes long backtests degrade.
   Same fix benefits the interpret path (its broker snapshot is 5.4 ms of the 42 ms run).
3. **Cheap secondary win:** per-tick context re-probe in interpret's
   `_snapshot_realtime_scope` (~139 bindings × 40 ticks); a cached
   "may-hold-container" set or bind-time tagging would reclaim most of ~4.8 ms/run.
4. **Not worth touching for perf:** object-mode inline scalar snapshot (≈µs), TA window
   snapshot (≤1.6 ms only on strategy), plot/tick plumbing.
5. Object-mode RT for indicator-class varip scripts is already good; spend effort on
   making sure strategies actually ship through compile mode (host already does this).

## 7. What was NOT measured / caveats

- Single machine, single process, synthetic seeded bars; no absolute cross-machine claims.
- RT window was last-10-bars × 5 ticks on 400 bars; cost scales with (RT bars × ticks)
  and, for the broker fix estimate, with cumulative event count (only 42 events here —
  the quadratic term would dominate in long/active backtests; the linear-regime win is the
  ~4.4 ms measured).
- No realtime `data_feed` (poll path) measured; no `request.security`, drawings, UDT-varip
  fields, maps, or matrices. Container math above covers list-backed Pine arrays only.
- cProfile numbers are for relative attribution only (profiler inflates); wall-clock deltas
  are the primary evidence.
- `A_numeric` RT (~2.0 ms) is consistently ~0.8 ms/call slower than native object-mode
  varip despite the re-emit being LRU-cached; cause not isolated (possibly re-emit path
  overhead in `CompiledScript.run`); noted, not explained, not decision-relevant.
- B2 scaling verified only to n=400; quadratic coefficient not precisely fitted.
- No correctness testing of any proposed fix — none was implemented. This is an analysis.
- Numeric-mode realtime remains impossible by construction (see docs/known_divergences.md
  §"Numeric nopython varip tick loop"); nothing here re-litigates that.
- First-call/cold numbers exclude OS page-cache effects across processes; in-process
  `use_cache=False` used as the cold proxy.

## 8. Reproduce

```bash
cd /mnt/data/home/jango/Git/hoox-open-trading-stack/pynescript
.venv/bin/python /tmp/varip_bench/bench.py             # wall-clock matrix
.venv/bin/python /tmp/varip_bench/probe_breakdown.py   # monkeypatched snapshot/restore timers
.venv/bin/python /tmp/varip_bench/probe_profile.py     # cProfile attribution
.venv/bin/python /tmp/varip_bench/probe_scale.py       # array-growth scaling + engine-level split
.venv/bin/python /tmp/varip_bench/recheck.py           # numeric re-emit anomaly re-check
```

Harness files live in `/tmp/varip_bench/` (not in repo). Raw JSON: `/tmp/varip_bench/results_timing.json`.
Repo untouched except this report; pre-existing `.prettierignore` modification left as-is.

### Key file references

- `src/pynescript/compiler/compiler.py:1397` — varip ⇒ object mode forcing
- `compiler.py:1746-1830` — object-mode prelude / tick snapshot-restore emit
- `src/pynescript/compiler/strategy_broker.py:421-461` — broker `snapshot()`/`restore()`
  (events dict-copy + `replace()` of all legs/records per tick)
- `compiler/strategy_broker.py` `to_events()` never drained mid-run; host packs events once
  at the end via `__events` (compiler.py:1627)
- `src/pynescript/runtime/host.py:1491` `_snapshot_realtime_scope`, `:1547` restore,
  `:1376` `_copy_container_contents` (one level of list/dict copy; 139 bindings probed per tick)
- interpret broker: `ast/evaluator/builtins/strategy.py:373` (same snapshot pattern)
- compile path never drains events per bar (contrast `host.py:2708` interpret drain)
