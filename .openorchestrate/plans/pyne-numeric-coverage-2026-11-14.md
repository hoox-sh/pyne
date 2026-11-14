# PYNE numeric-mode (Numba) coverage — gap inventory + first slice

- **Date:** 2026-11-14
- **Seat:** `oo-spec-2` (Engineering)
- **Card:** `pyne-compile-widen-numeric-mode--ee110c5f` (HQ board)
- **Repo:** `/mnt/data/home/jango/Git/hoox-open-trading-stack/pynescript`
- **Status:** inventory complete; first slice implemented and verified; **not committed / not pushed**.
- **Scope:** read-only inventory for realtime/varip and drawings/UDT/methods (no code there).

## TL;DR

- `CompilerVisitor` has **184** `self.object_mode = True` assignment sites across **34**
  functions (`src/pynescript/compiler/compiler.py`). 226 total `object_mode` references.
- Numeric mode is not the default in practice: in a static transpile-only scan of
  `set01+set02` (494 scripts), **449/450 parseable scripts were object mode, 1 numeric**
  before this slice; **448/450 object, 2 numeric** after.
- The highest-frequency *unnecessary* flip with a safe fix was literal `color.new(...)`:
  723/2,477 set01–04 scripts use `color.new`; 77 scripts use it with no other obvious
  object-only construct. Constant-folding literal colors moved **7/77** of those from
  object to numeric, with **6 clean interpret↔compile parity** results and one
  pre-existing interpret mismatch (`ttm_wave`, unchanged by this slice).
- Top remaining blockers in the 77-script target set: assigned `hline` (48 scripts
  corpus-wide), `input.*` type tokens (115), `nz()` on numeric UDF series params
  (741 scripts use `nz`), `runtime.error` (563), and visual events
  (`bgcolor` 354, `plotshape` 359).
- **Recommended order for the other cards:** #2 realtime/varip first (correctness on the
  live path), then #3 starting with library/exported methods + UDT overload dispatch,
  then drawing realtime rollback.

## Method and evidence

1. **Static flip inventory.** Parsed `compiler.py` with `ast`, found every
   `self.object_mode = True`, recorded line, enclosing function, and nearest branch.
   Full appendix at the end.
2. **Dynamic flip frequency.** Traced `sys.settrace` line events for the flip lines while
   transpiling a fixed random sample of 55 set01–03 scripts (5 parse errors). This gives
   execution frequency, not just source presence.
3. **Corpus scan.** `_transpile_once` (parse + visitor, no Numba JIT) over `set01+set02`
   before/after; 494 files, 450 parseable, 44 parse errors (scraped docs/chrome).
4. **Counterfactual targeting.** A `CompilerVisitor` subclass with an `object_mode`
   property suppressed one flip line at a time to measure which construct actually
   unlocks numeric mode. This avoided guessing from source presence.
5. **Parity.** `scripts/compare_interp_compile.py` on the 7 unlocked scripts + controls,
   120 bars, `--strict-errors`.

### Repo state (no commits or pushes by this seat)

- HQ `HEAD`: `ae25ed442b2275430d7c876fa6a660081291422c`.
- `pynescript` started this run at `d4b3bee10a60d48dabc55ae076b8f96d0a07bbec`; another
  seat landed `3495108b` and `f77f054f` (data-feed fixes, `backend/api/data_series.py`
  only) while this inventory ran. Current `HEAD`: `f77f054fc7d66fc72aeb2d71e6c888cc58c8ea36`.
  Neither commit touches the compiler.
- Pre-existing dirty/untracked in `pynescript`: `.openorchestrate/board.md` (M),
  `.openorchestrate/plans/` (untracked), `.openorchestrate/proof/` (untracked).
- This slice adds: `src/pynescript/compiler/compiler.py` (M),
  `tests/test_compiler_color_fold.py` (new), and this plan/proof.

## Grouped gap matrix

Current mode is the mode a script containing the construct lands in unless another
construct flips it earlier. "Numba-representable?" means *could* the construct be
lowered to njit float64/int64 with work, not whether the current emitter does.

| # | Construct group | Examples | Current mode | Why / flip sites | Numba-representable? |
| ---: | --- | --- | --- | --- | --- |
| 1 | UDT declaration / use | `type`, `.new`, field get/set, UDT series | object | `compiler.py:1554, 2130, 2178, 2321, 4307, 7771`; dict representation | Partial — typed struct/arrays possible, high effort |
| 2 | Enums | `enum`, `Dir.Up` | object | `compiler.py:1579, 1955, 4229` | Yes as int constants, medium |
| 3 | Maps | `map.new/get/put`, `for [k,v] in m` | object | `compiler.py:2110, 2296, 5183, 5212, 5672, 10428` | Partial — typed dict; string/UDT values block |
| 4 | Arrays / matrices | `array.*`, `matrix.*`, method forms | object | `compiler.py:2346, 5130, 5170, 5208, 5216, 5247, 5683` | Partial — homogeneous numeric typed arrays; high effort |
| 5 | Drawings / visual events | `label/line/box/table/polyline/linefill`, `plotshape`, `bgcolor`, `barcolor` | object | `compiler.py:531-558, 4116, 5475, 5520, 5616, 5648, 5667` | Partial — numeric condition + constant attrs can synthesize events; medium |
| 6 | Strategy | `strategy(...)`, entry/exit/risk/query attrs | object | `compiler.py:4268, 4272, 4889, 4910, 4919, 5377, 7580, 7685, 7721` | No — Python broker state |
| 7 | String/color **series** | ternary colors, string series, color arithmetic | object | `compiler.py:2226, 2251, 2280, 4078, 8268, 8281` | No for series (unicode/pyobject); constant metadata foldable |
| 8 | `str.*` builtins | `str.tostring/format/lower/...` | object | `compiler.py:5840-5935` | No — unicode ops |
| 9 | Alerts | `alert`, `alertcondition` | object | `compiler.py:1341, 4078` | Partial — numeric condition + constant message can synthesize `__alerts`; medium |
| 10 | String/color inputs | `input.string/color/symbol/timeframe/session` | object | `compiler.py:5410, 5416, 5426` | No — string scalar |
| 11 | Numeric/bool/source inputs via `input.*` type token | `input(14, type=input.integer)`, `type=input.source` | object today | `compiler.py:3993, 3996, 4003, 4346` | **Yes** — token is metadata; follow-up |
| 12 | Namespace/type tokens as values | `syminfo.*`, `timeframe.*`, `hline.style_*`, `input.*` | object | `compiler.py:4948-4987, 3993` | Mixed — strings no; `timeframe.in_seconds`, input tokens yes |
| 13 | `runtime.error` | guards in numeric indicators | object | `compiler.py:5700`; `pine_raise` is plain Python (`numba_builtins.py:2260`) | Partial — needs njit-safe raise; medium |
| 14 | `request.*` / footprint / volume_row | foreign data, mocks | object | `compiler.py:6043-6064` | No — stubs / external data |
| 15 | `security` with UDT/complex expression | `request.security(..., udt)` | object | `compiler.py:6043, 8706` | No — object handle |
| 16 | `once` inside a UDF | UDF-scoped once | object | `compiler.py:1388` | Yes via array flag, low frequency |
| 17 | UDF needs `data_feed` / `__strategy` / `__drawings` | feed/strategy/drawing in UDF | object | `compiler.py:9833, 9899, 9905` | No — Python handles |
| 18 | Tuple / sequence returns | list/tuple handles, `a = f()` | object | `compiler.py:2196, 2373, 3241-3574, 3309` | No — lists; numeric tuples already separate |
| 19 | Unsafe assignment / reassign | non-numeric RHS, `safe_float`, UDT call | object | `compiler.py:2382, 2401, 3777, 3780` | Fail-closed; **false positives** for `nz(src)` series params |
| 20 | Assigned `hline` / expression `fill` | `h = hline(50)`, `fill(p1,p2)` | object | `compiler.py:5475, 5520` | Yes — handle is metadata; 48 hline-assigned scripts |
| 21 | `plot` non-numeric source | UDT/string/handle source | object | `compiler.py:5581` | No unless source is numeric |
| 22 | `switch`/`if` object-valued assignment | statement switch/if returning object | object | `compiler.py:9036, 9074, 9228, 9297` | No — Python control flow |
| 23 | `for-in` map/UDT | `for [k,v] in m` | object | `compiler.py:10428` | No |
| 24 | `ticker.*` / library import | `ticker.new`, `import` | object | `compiler.py:1053, 5348, 5359, 5372` | No — stubs |
| 25 | `color.from_gradient` / `color.rgb` | color helpers | object | `compiler.py:5707, 7027` | Partial — numeric color code; medium |
| 26 | Calendar `timeframe.change` | `D/W/M` | object | `compiler.py:5767, 5774` | No — tz rules outside njit |
| 27 | Unknown calls / library methods | `alias.method(...)` | object | `compiler.py:7129, 7141` | No — stubs |
| 28 | Object cell materialization | non-array series source | object | `compiler.py:1028` | No — object cells |
| 29 | Backend safety net / forced recovery | residual handles, nopython fallback | object | `compiler.py:621, 1091, 1093`; `engine.py:791` | No — recovery path |

### Actual flip frequency (55-script trace sample, current line numbers)

| Executions | Flip line | Construct |
| ---: | --- | --- |
| 501 | `compiler.py:2401` | unsafe RHS store → `safe_float` |
| 394 | `compiler.py:2251` | string/color RHS assignment |
| 381 | `compiler.py:5683` | `array.*` / `matrix.*` |
| 361 | `compiler.py:5616` | drawing setters (`label.set_*`, …) |
| 206 | `compiler.py:5667` | drawing constructors / visual funcs |
| 185 | `compiler.py:8268` | string/color `BinOp` |
| 180 | `compiler.py:2226` | string constant assignment |
| 172 | `compiler.py:5410` | string/color input |
| 134 | `compiler.py:3737` | drawing handle reassign |
| 131 | `compiler.py:5855` | `str.tostring` |
| 129 | `compiler.py:6904` | `nz()` with stringy/unsafe arg |
| 117 | `compiler.py:4307` | UDT/object field access |
| 90 | `compiler.py:1341` | alert / alertcondition |
| 84 | `compiler.py:5581` | `plot` non-numeric source |
| 83 | `compiler.py:2154` | drawing/collection scalar |
| 82 | `compiler.py:5740` | **dynamic** `color.new` (literal colors folded by this slice; was 240 pre-slice) |
| 75 | `compiler.py:4889` | strategy attr |
| 66 | `compiler.py:3777` | unsafe reassign |
| 65 | `compiler.py:3742` | string/UDT reassign |
| 58 | `compiler.py:5869` | `str.length` |

All 55 parsed scripts still ended object mode: the corpus is dominated by drawings,
strings, arrays, and UDTs, so removing one flip rarely changes the final mode. The
77-script target set is the honest addressable measure for this slice.

## Compile blockers (not object-mode flips)

| Blocker | Evidence | Effect |
| --- | --- | --- |
| Top-level `import` | `runtime/host.py:4200-4201` | `mode=auto` skips compile; explicit compile still attempts |
| Any `request.` token | `runtime/host.py:4202-4203` | `mode=auto` skips compile even for same-symbol simple security |
| `input.*` overrides | `runtime/host.py:4282` | compile skipped when inputs are overridden |
| Numba missing | `compiler/engine.py:1320, 1359-1360` | `CompileNumbaRequiredError` for pure numeric emit |
| Parse failure | `compiler/engine.py:1148-1151` | `CompileEmitError`; 44/494 set01–02 scraped files |
| nopython typing failure | `compiler/engine.py:1090-1122, 765-807` | re-emit object mode once; `nopython_fallback_reason` |
| Unsupported AST / empty emit | `compiler/engine.py:1154-1156` | `CompileEmitError` |

## Chosen slice — literal `color.new` / `color()` constant folding

### Why this slice

- `color.new` is used by **723/2,477** set01–04 scripts (29%).
- It is a metadata value in the dominant `plot(..., color=color.new(...))` and
  `fill(..., color=color.new(...))` forms; the bar loop never needs the string.
- The old branch set `self.object_mode = True` before even checking whether the
  base/transparency were literals (`compiler.py:5716-5726` pre-slice).
- 77 scripts use `color.new` with no other obvious object-only construct; 7 of them
  become numeric with only this change. This is the largest safe unlock found.
- Dynamic colors (series/input expressions) still take the old object-mode path.

### Implementation

`src/pynescript/compiler/compiler.py` (current lines 5730-5770):

- Fold only while resolving `plot`/`fill`/`hline` arguments (`_fold_literal_color`,
  `compiler.py:5234-5252`). Object-only call sites (`bgcolor`, drawings) and
  assigned colors keep the legacy `pine_color_new(...)` helper and object mode.
- Resolve `base` from positional arg or `color=` kwarg; resolve `transp` from
  kwarg or second positional.
- If both fold to literals via `_fold_const`, call `pine_color_new` at **transpile
  time** and emit a quoted literal; do not set `object_mode`.
- Otherwise set `object_mode` and keep the old runtime helper.

This preserves the exact color string produced by object mode because it calls the
same `pine_color_new` (`compiler/numba_builtins.py:2456`).

### Tests

`tests/test_compiler_color_fold.py` — 5 tests:

1. literal plot color stays numeric, no `pine_color_new` in generated code;
2. literal `fill` color folds into `plot_attrs["color"]` (`rgba(...)`);
3. keyword `color=` + hex base fold;
4. dynamic transparency stays object mode;
5. color series stays object mode.

### Before / after

| Measure | Before | After |
| --- | ---: | ---: |
| `set01+set02` static scan: parseable | 450 | 450 |
| `set01+set02`: object mode | 449 | **448** |
| `set01+set02`: numeric mode | 1 | **2** |
| 77 `color.new`-only candidates: numeric | 0 | **7** |
| 77 candidates: object | 75 | 68 |
| 77 candidates: parse errors | 2 | 2 |
| 55-script trace: `color.new` flip executions | 240 | **82** |
| `test_compiler_numba.py` | 210 passed | 210 passed |
| new color-fold tests | — | 7 passed |
| targeted combined suite | — | **306 passed** |

The 7 unlocked scripts:

- `set01/indicators/205_ind_supertrend_from_scratch.pine`
- `set03/indicators/0449_ind_ttm_wave_ttm_wave.pine`
- `set04/indicators/0740_ind_plot_fill_demo.pine`
- `set04/indicators/0258_ind_accumulation_swing_index_asi_2.pine`
- `set04/indicators/0699_ind_example_2.pine`
- `set04/indicators/0909_ind_plot_2.pine`
- `set04/indicators/0257_ind_accumulation_swing_index_asi.pine`

Parity run: **14 unique scripts** (7 unlocked + 7 controls), 120 bars,
`--strict-errors`: **13 OK, 1 MISMATCH, 0 compile/interp errors**. The mismatch is
`ttm_wave`: numeric and forced-object compile produce identical values
(`Wave A1[1]=0.1556462585033874`), so the interpret↔compile divergence predates
this slice and is not a regression. It is recorded here, not hidden.
`parity_14.json` is authoritative; the earlier `parity_15.json` contained a
duplicate `0740_ind_plot_fill_demo` entry and is superseded.

**Plot_meta check (hline attrs).** The numeric hline synthesizer originally
emitted only `kind/bar/title/price`, so `0449`, `0258`, and `0257` lost their
hline color/linestyle in `plot_meta`. Fixed by folding hline `color`/`linestyle` into `plot_attrs`
(`compiler.py:118-124`, `compiler.py:7953-7958`), passing `plot_attrs` through
`_synthesize_hline_fill_drawings` (`engine.py:948-986`), and stamping those
fields on each synthesized event. Disk IR meta bumped to v54 (`engine.py:182`)
so stale cached `plot_attrs` cannot mask the fix. Numeric compile now matches forced-object compile for all three:

| script | hline | color | linestyle (compile object = numeric) |
| --- | --- | --- | --- |
| `0449_ind_ttm_wave_ttm_wave` | Zero | `#787B86` | `style_dotted` |
| `0258_ind_accumulation_swing_index_asi_2` | Zero Line | `rgba(120, 123, 134, 0.4)` | `style_dashed` |
| `0257_ind_accumulation_swing_index_asi` | Zero Line | `rgba(120, 123, 134, 0.4)` | `style_dashed` |

Interpret normalizes linestyle to `dotted`/`dashed`; compile object/numeric use
`style_dotted`/`style_dashed`. That normalization difference predates this slice;
the fix is compile object↔numeric parity.

### Follow-up ranking (from the same counterfactual data)

1. `input.*` type tokens (`type=input.integer/float/bool/source`) — 115 scripts;
   only 2 strict candidates; clean compile-time metadata fix.
2. `nz()` on numeric UDF series params — 741 scripts use `nz`; `_is_safe_numeric_expr`
   only strips `*_arr[...]`, not `param[__bar_idx]` (`compiler.py:2924-2949, 3004-3013`).
3. Assigned `hline` (`h = hline(...)`) — 48 scripts; numeric synthesis already exists
   for statement form (`compiler.py:5475`).
4. `runtime.error` — 563 scripts; needs an njit-safe raise path.
5. Visual events (`bgcolor` 354, `plotshape` 359) — larger feature; numeric condition +
   constant attrs can synthesize events like statement `hline`/`fill`.

## #2 — realtime / `varip` semantics (read-only inventory)

### Current behavior

| Layer | Behavior | Evidence |
| --- | --- | --- |
| Host API | `Runtime.run(..., realtime_last_bar=, realtime_ticks=, realtime_bars=, realtime_from_bar=)` resolves a window and forwards `rt_first`/`rt_ticks` | `runtime/host.py:1752-1789, 2231-2238` |
| Interpret tick loop | Re-visits forming bars; `__isrealtime`/`__ishistory`/`__isnew`/`__isconfirmed` set per tick | `runtime/host.py:2397-2512` |
| Interpret rollback | Snapshots `var` scope + containers + series `.current`; restores after unconfirmed tick; `varip` names excluded | `runtime/host.py:1377-1478, 2465-2505` |
| Object compile tick loop | Same window semantics; `varip` re-inits on `__isrealtime`, `var` commits on confirmed tick; drawings truncated, broker snapshot/restore | `compiler/compiler.py:1489-1550, 1419-1423, 1449-1488` |
| Numeric compile | No tick loop; `__isrealtime=False`, `__isconfirmed=True`, `__ishistory=True`, `__isnew=True` constants | `compiler/compiler.py:1412-1417` |
| Numeric + active window | Host re-compiles with `force_object_mode=True` before running | `runtime/host.py:4501-4505` |
| `varip` numeric | `_var_init_cond` checks `__isrealtime`, but numeric never sets it true; `varip` behaves like `var` | `compiler/compiler.py:1419-1423` |
| `once` | Interpret/object compile latch only when `__isconfirmed`; numeric is always historical | `compiler/compiler.py:9442-9458`; `docs/known_divergences.md:154` |
| Data feed | Object/interpret poll `poll_forming_ohlcv` per tick; numeric does not poll | `compiler/compiler.py:1513-1521`; `docs/known_divergences.md:160-162` |

### Top 3 gaps

1. **Numeric nopython has no realtime semantics.** Any active realtime window forces
   object mode (`runtime/host.py:4501-4505`), so numeric scripts lose njit speed and
   `varip` is indistinguishable from `var` in numeric emit (`compiler.py:1412-1423`).
   This is the largest structural gap and the reason "full realtime/varip" cannot be
   claimed while numeric mode is the fast path.
2. **Interpret rollback is best-effort, not a generic deep copy.** Only one extra
   list/dict nesting level is copied; Matrix/Map/UDT internals are best-effort
   (`runtime/host.py:1377-1478`; `docs/known_divergences.md:156`). Deep nested
   `var` containers can leak mutations from unconfirmed ticks.
3. **No intra-bar tick path for broker fills/trails/MAE-MFE.** Pending OHLC fills run
   once per bar before the tick loop; trail/MAE-MFE are OHLC-path approximations;
   `CCXTProDataFeed.poll_ohlcv` returns the last cached candle, not a live tick stream
   (`docs/known_divergences.md:158-162`; D-01/D-03 rows 20-22). Numeric `once` also
   stays historical (`compiler.py:9442-9458`).

## #3 — drawings, UDT, methods (read-only inventory)

### Current behavior

| Layer | Behavior | Evidence |
| --- | --- | --- |
| Drawings | All constructors/mutators force object mode; events appended to `__drawings` | `compiler.py:531-558, 5616, 5648, 5667, 8060-8229` |
| Drawing export | Compile emits append-only geometry events; runtime lifts to series/plot_meta and trims by declaration caps | `compiler.py:1162-1320`; `runtime/host.py:4554-4595` |
| Drawing getters | `line.get_price`, `label.get_text`, etc. object-mode only | `compiler.py:5630-5666` |
| UDT | Instances are ordered-field dicts; `.new`, field get/set, `Type.copy` shallow copy | `compiler.py:7769-7800, 5094-5113`; docstring lines 29-31 |
| UDT series | Object-dtype arrays; `udt_get_field`/`udt_set_field` | `compiler.py:2178, 2321, 4307` |
| UDT methods | `method`/`export` forces object mode; receiver type from first formal | `compiler.py:9546, 671-674` |
| Method overloads | Arity first, then receiver/arg type score; fallback = last candidate | `compiler.py:7374-7429, 7336-7355` |
| Type inference | Heuristic from AST/visited expr; returns `None` when unknown | `compiler.py:7202-7287, 7288-7334` |
| Library methods | Imported `alias.method(...)` are stubs (`np.nan`/`None`), not executed | `compiler.py:5031, 5089, 7129, 7144` |
| UDT collections | `array.sort_field` / `binary_search*` supported; object mode | `docs/pine_v6_full_surface_inventory.md:214-215, 479-481` |

### Top 3 gaps

1. **Library/exported methods are not executed on compile.** Any `export`/`method`
   forces object mode (`compiler.py:9546`), and imported library method calls are
   stubbed to `np.nan`/`None` (`compiler.py:7129, 7144`). This is a correctness gap,
   not just performance: a library-based indicator can silently return `na` on compile.
2. **UDT/method overload dispatch is heuristic and can silently pick the wrong
   implementation.** `_resolve_user_func_overload` falls back to the last same-arity
   candidate when receiver/arg type inference fails (`compiler.py:7374-7429`);
   `_receiver_type_from_expr` returns `None` for many call results, array elements,
   and chained expressions (`compiler.py:7288-7334`). Same-arity overloads on
   `float`/`bool`/`color`/UDT can misdispatch with no error.
3. **Drawing state is not rolled back on unconfirmed realtime ticks.** The tick
   snapshot only records `len(__drawings)` and truncates newly appended events
   (`compiler.py:1452, 1475`); in-place mutations to existing drawing dicts
   (`line.set_xy`, `label.set_text`, `delete`) are not restored. Compile drawings are
   also append-only geometry events, so `label.all`/GC/`get_price` semantics remain
   object-mode-only (`compiler.py:4116, 5630-5666`; `runtime/host.py:4587-4595`).

## Recommended order

1. **#2 realtime/varip** — correctness on the live path. Start with a numeric-mode
   tick loop or an explicit, documented "numeric is historical only" contract plus
   `varip` parity tests; then deepen interpret rollback beyond one nesting level.
2. **#3 drawings/UDT/methods** — start with library/exported method execution and
   overload-dispatch errors (silent `na`/wrong method are correctness bugs), then
   drawing realtime rollback, then numeric drawing synthesis.
3. **#1 follow-ups** — `input.*` tokens, `nz()` series-param recognition, assigned
   `hline`, then visual events. These are compile-performance/coverage wins, not
   live-correctness wins.

## Appendix — every `self.object_mode = True` site

Generated from `src/pynescript/compiler/compiler.py` at current `HEAD` + working tree.
Line numbers are current; the nearest branch is the last `if`/`elif` before the
assignment (blank when the assignment is unconditional in its function).

| line | function | nearest branch |
| ---: | --- | --- |
| 621 | `__init__` | `` |
| 1028 | `_materialize_series_source` | `if self.in_function and self._current_func_name:` |
| 1053 | `visit_Import` | `if alias:` |
| 1091 | `visit_Script` | `if self.string_series or self.udt_vars or self.map_vars or _obj_scalars:` |
| 1093 | `visit_Script` | `if self.force_object_mode:` |
| 1341 | `_emit_alert_call` | `` |
| 1388 | `_alloc_once_flag` | `if self.in_function:` |
| 1554 | `visit_TypeDef` | `if self.uses_strategy:` |
| 1579 | `visit_EnumDef` | `if field_types:` |
| 1939 | `visit_Assign` | `if isinstance(node.target, ast.Attribute):` |
| 1955 | `visit_Assign` | `if type_id_early and type_id_early in self.enum_types:` |
| 2093 | `visit_Assign` | `if (` |
| 2110 | `visit_Assign` | `if self._is_map_new(node.value) or self._is_typed_map(type_node):` |
| 2118 | `visit_Assign` | `if hasattr(self, "_rhs_is_sequence") and self._rhs_is_sequence(node.value, val):` |
| 2130 | `visit_Assign` | `if typed_udt or self._looks_like_udt_ctor(node.value) or self._val_looks_like_udt_dict(val):` |
| 2144 | `visit_Assign` | `if name in self.user_funcs or name in self._pre_func_names:` |
| 2154 | `visit_Assign` | `if typed_drawing or typed_collection:` |
| 2178 | `visit_Assign` | `if typed_udt or typed_chart_point:` |
| 2196 | `visit_Assign` | `if hasattr(self, "_rhs_is_sequence") and self._rhs_is_sequence(node.value, val):` |
| 2226 | `visit_Assign` | `if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):` |
| 2251 | `visit_Assign` | `if is_stringy_rhs:` |
| 2280 | `visit_Assign` | `if name in self.string_series:` |
| 2296 | `visit_Assign` | `if self._is_map_new(node.value) or self._is_typed_map(type_node):` |
| 2321 | `visit_Assign` | `if not rhs_is_drawing and (` |
| 2338 | `visit_Assign` | `if self._is_drawing_new(node.value) or self._looks_like_drawing_handle_expr(val):` |
| 2346 | `visit_Assign` | `if self._is_array_or_matrix_handle(node.value):` |
| 2373 | `visit_Assign` | `if self._looks_like_sequence_expr(val) or self._is_sequence_producing_call(node.value):` |
| 2382 | `visit_Assign` | `if val and (val.startswith("safe_float(") or val.startswith("safe_int(")):` |
| 2401 | `visit_Assign` | `if not self.in_function and (` |
| 3241 | `_visit_tuple_assign` | `if pine_name in self.user_funcs:` |
| 3267 | `_store_numeric` | `if py != name and py.endswith("__loc"):` |
| 3274 | `_store_numeric` | `if self._looks_like_string_expr(expr):` |
| 3286 | `_store_kept` | `if self.object_mode:` |
| 3309 | `_store_sequence` | `if kind == "string":` |
| 3397 | `_visit_tuple_assign` | `if expr_node is not None and len(names) > 1:` |
| 3423 | `_visit_tuple_assign` | `if not call_code:` |
| 3530 | `_visit_tuple_assign` | `if not numeric_udf and not numeric_tuple_udf:` |
| 3563 | `_visit_tuple_assign` | `if isinstance(node.value, ast.If):` |
| 3568 | `_visit_tuple_assign` | `if rhs and (rhs.lstrip().startswith("if ") or "\n" in rhs):` |
| 3574 | `_visit_tuple_assign` | `if rhs and len(names) > 1:` |
| 3657 | `visit_ReAssign` | `if isinstance(node.target, ast.Attribute):` |
| 3692 | `visit_ReAssign` | `if val and (` |
| 3737 | `visit_ReAssign` | `if (` |
| 3742 | `visit_ReAssign` | `if name in self.string_series or name in self.udt_vars:` |
| 3747 | `visit_ReAssign` | `if isinstance(node.value, ast.Name) and node.value.id in self.udt_vars:` |
| 3757 | `visit_ReAssign` | `if (` |
| 3763 | `visit_ReAssign` | `if hasattr(self, "_rhs_is_sequence") and self._rhs_is_sequence(node.value, val):` |
| 3777 | `visit_ReAssign` | `if not self._is_safe_numeric_expr(val):` |
| 3780 | `visit_ReAssign` | `elif self._looks_like_sequence_expr(val) or self._val_looks_like_udt_dict(val):` |
| 3822 | `visit_AugAssign` | `if isinstance(node.target, ast.Attribute):` |
| 3869 | `visit_Name` | `if node.id in ("tickerid", "ticker") and node.id not in self.ident_map:` |
| 3891 | `visit_Name` | `if node.id == "color":` |
| 3934 | `visit_Name` | `if node.id == "tz":` |
| 3938 | `visit_Name` | `if node.id in _COLOR_NAMES:` |
| 3943 | `visit_Name` | `if node.id in _LINESTYLE_NAMES:` |
| 3957 | `visit_Name` | `if ident is not None:` |
| 3993 | `visit_Name` | `if node.id in _NS and node.id not in (self.map_vars \| self.scalar_vars):` |
| 3996 | `visit_Name` | `if node.id in _STUB_NS and node.id not in (self.map_vars \| self.scalar_vars):` |
| 4003 | `visit_Name` | `if (` |
| 4030 | `visit_Name` | `if node.id in self.import_aliases:` |
| 4078 | `visit_Attribute` | `if isinstance(node.value, ast.Name) and node.value.id == "alert":` |
| 4116 | `visit_Attribute` | `if node.attr == "all":` |
| 4205 | `visit_Attribute` | `if isinstance(node.value, ast.Name) and node.value.id in _STUB_NS:` |
| 4229 | `visit_Attribute` | `if isinstance(node.value, ast.Name) and node.value.id in self.enum_types:` |
| 4243 | `visit_Attribute` | `if nm in self.local_vars or nm in self.udt_vars or nm in self.scalar_vars or nm in self.loop_counters:` |
| 4268 | `visit_Attribute` | `if parent == "opentrades" and node.attr == "capital_held":` |
| 4272 | `visit_Attribute` | `if parent == "closedtrades" and node.attr == "first_index":` |
| 4288 | `visit_Attribute` | `if "__u :=" in val or "isinstance(__u" in val or "udt_get_field(" in val:` |
| 4294 | `visit_Attribute` | `if isinstance(node.value, ast.Call):` |
| 4303 | `visit_Attribute` | `if (` |
| 4307 | `visit_Attribute` | `if self.object_mode or (isinstance(node.value, ast.Name) and node.value.id in self.udt_vars):` |
| 4346 | `visit_Attribute` | `if attr in ("max", "min"):` |
| 4889 | `_emit_strategy_attr` | `if attr in series_map:` |
| 4910 | `_emit_strategy_attr` | `if attr in (` |
| 4919 | `_emit_strategy_attr` | `if attr in ("oca", "commission", "direction", "risk", "avg_price"):` |
| 4948 | `_timeframe_compile_expr` | `if attr == "in_seconds":` |
| 4951 | `_timeframe_compile_expr` | `if attr in self._TIMEFRAME_ATTRS:` |
| 4963 | `_syminfo_compile_expr` | `if attr == "ticker":` |
| 4966 | `_syminfo_compile_expr` | `if attr in ("tickerid", "root"):` |
| 4969 | `_syminfo_compile_expr` | `if attr == "prefix":` |
| 4987 | `_syminfo_compile_expr` | `if val.startswith("'") or val.startswith('"') or val.startswith("chart_"):` |
| 5094 | `visit_Call` | `elif isinstance(func.value, ast.Name) and func.value.id in self.udt_types and func.attr == "copy":` |
| 5113 | `visit_Call` | `elif isinstance(func.value, ast.Name) and func.value.id in self.udt_vars and func.attr == "copy":` |
| 5130 | `visit_Call` | `elif func.attr in _ARRAY_METHODS and self._call_prefers_array_method(func):` |
| 5143 | `visit_Call` | `elif (` |
| 5170 | `visit_Call` | `if recv_is_array_name or not looks_series:` |
| 5183 | `visit_Call` | `elif func.attr in _MAP_METHODS and self._call_is_map_method(func, node):` |
| 5192 | `visit_Call` | `elif (` |
| 5199 | `visit_Call` | `elif (` |
| 5208 | `visit_Call` | `elif func.attr in _ARRAY_METHODS:` |
| 5212 | `visit_Call` | `elif func.attr in _MAP_METHODS:` |
| 5216 | `visit_Call` | `elif func.attr in _TABLE_METHODS:` |
| 5221 | `visit_Call` | `elif func.attr in _TABLE_METHODS:` |
| 5247 | `visit_Call` | `if method_src is None and func_name in _BARE_COLLECTION:` |
| 5281 | `visit_Call` | `if _chart_point_ctor:` |
| 5340 | `visit_Call` | `if func_name in ("modify", "ticker_modify"):` |
| 5348 | `visit_Call` | `if func_name == "ticker_new":` |
| 5359 | `visit_Call` | `if func_name.startswith("ticker_"):` |
| 5372 | `visit_Call` | `if func_name == "library":` |
| 5377 | `visit_Call` | `if func_name == "strategy":` |
| 5410 | `visit_Call` | `if defval is not None and (` |
| 5416 | `visit_Call` | `if func_name in ("input_string", "input_text_area"):` |
| 5426 | `visit_Call` | `if func_name in (` |
| 5475 | `visit_Call` | `if stmt and price_ok and not self.object_mode:` |
| 5520 | `visit_Call` | `if getattr(self, "_stmt_expr", False) and not self.object_mode:` |
| 5581 | `visit_Call` | `if needs_safe and not series_expr.startswith("safe_float("):` |
| 5616 | `visit_Call` | `if (` |
| 5648 | `visit_Call` | `if (` |
| 5667 | `visit_Call` | `if func_name in _DRAWING_FUNCS or (` |
| 5672 | `visit_Call` | `if func_name not in self.user_funcs and self._safe_ident(func_name) not in self.user_funcs:` |
| 5683 | `visit_Call` | `if (` |
| 5689 | `visit_Call` | `if func_name.startswith("console_"):` |
| 5700 | `visit_Call` | `if func_name in ("runtime_error", "runtime_error_code"):` |
| 5707 | `visit_Call` | `if func_name == "color_from_gradient":` |
| 5740 | `visit_Call` | `if isinstance(folded, str):` |
| 5751 | `visit_Call` | `if func_name == "timeframe_from_seconds":` |
| 5767 | `visit_Call` | `if timeframe_is_calendar_tf(inner):` |
| 5774 | `visit_Call` | `if bucket is not None:` |
| 5816 | `visit_Call` | `if method_src is not None and self._udf_formal_count(func_name) == 0:` |
| 5834 | `visit_Call` | `if func_name in (` |
| 5840 | `visit_Call` | `if func_name == "str_split":` |
| 5847 | `visit_Call` | `if func_name in ("sequence_from_series",) or func_name.endswith("_sequence_from_series"):` |
| 5855 | `visit_Call` | `if func_name in ("str_tostring", "tostring"):` |
| 5858 | `visit_Call` | `if func_name == "str_format":` |
| 5866 | `visit_Call` | `if func_name == "str_length":` |
| 5869 | `visit_Call` | `if func_name == "str_contains":` |
| 5874 | `visit_Call` | `if func_name == "str_startswith":` |
| 5879 | `visit_Call` | `if func_name == "str_endswith":` |
| 5884 | `visit_Call` | `if func_name in ("str_replace_all", "str_replace"):` |
| 5889 | `visit_Call` | `if func_name == "str_lower":` |
| 5892 | `visit_Call` | `if func_name == "str_upper":` |
| 5895 | `visit_Call` | `if func_name == "str_trim":` |
| 5898 | `visit_Call` | `if func_name == "str_repeat":` |
| 5904 | `visit_Call` | `if func_name == "str_format_time":` |
| 5909 | `visit_Call` | `if func_name in ("str_tonumber", "tonumber"):` |
| 5914 | `visit_Call` | `if func_name in ("str_substring", "substring"):` |
| 5925 | `visit_Call` | `if func_name in ("str_pos", "pos"):` |
| 5930 | `visit_Call` | `if func_name in ("str_startswith", "startswith"):` |
| 5935 | `visit_Call` | `if func_name in ("str_endswith", "endswith"):` |
| 5941 | `visit_Call` | `if func_name == "sequence_from_series":` |
| 5950 | `visit_Call` | `if func_name == "sequence_float":` |
| 5961 | `visit_Call` | `if func_name in ("index_2d_to_1d", "index_1d_to_2d"):` |
| 5987 | `visit_Call` | `if named_act or positional_act:` |
| 6013 | `visit_Call` | `if inner:` |
| 6043 | `visit_Call` | `if func_name in ("security", "request_security") and self._security_expr_is_udt(node, expr):` |
| 6049 | `visit_Call` | `if func_name == "request_footprint":` |
| 6052 | `visit_Call` | `if func_name.startswith("request_"):` |
| 6056 | `visit_Call` | `if func_name.startswith("footprint_"):` |
| 6064 | `visit_Call` | `if func_name.startswith("volume_row_"):` |
| 6904 | `visit_Call` | `if (` |
| 6915 | `visit_Call` | `if self._looks_like_string_expr(arg) or arg in self.string_series or arg in self.string_scalars:` |
| 6921 | `visit_Call` | `if func_name in ("complex_new", "complex_arr_new"):` |
| 6974 | `visit_Call` | `if self.object_mode or not self._is_safe_numeric_expr(args[0]):` |
| 6988 | `visit_Call` | `if self.object_mode or not self._is_safe_numeric_expr(args[0]):` |
| 7007 | `visit_Call` | `if self.object_mode or not self._is_safe_numeric_expr(a0):` |
| 7012 | `visit_Call` | `if needs_safe:` |
| 7027 | `visit_Call` | `if func_name == "color_rgb":` |
| 7082 | `visit_Call` | `if self._is_safe_numeric_expr(arg) and not self.object_mode:` |
| 7098 | `visit_Call` | `if func_name == "string":` |
| 7105 | `visit_Call` | `if self.object_mode or not self._is_safe_numeric_expr(a0):` |
| 7111 | `visit_Call` | `if self.object_mode or not self._is_safe_numeric_expr(a0):` |
| 7117 | `visit_Call` | `if func_name in ("init", "console_init") or func_name.endswith("_init"):` |
| 7128 | `visit_Call` | `if func_name in (` |
| 7131 | `visit_Call` | `if func_name in ("array_range",) or (func_name.endswith("_range") and "array" in func_name):` |
| 7141 | `visit_Call` | `if args:` |
| 7580 | `_emit_strategy_call` | `if _meta(self.func_needs_strategy, False):` |
| 7685 | `_emit_strategy_risk_call` | `` |
| 7721 | `_emit_strategy_trade_query` | `if risk == "max_intraday_filled_orders":` |
| 7771 | `_emit_udt_new` | `if attr in ("comment",):` |
| 8268 | `visit_BinOp` | `if (left_str or right_str) and not (left_num and right_num):` |
| 8281 | `visit_BinOp` | `if (` |
| 8706 | `_emit_chart_htf_security` | `elif off is not None:` |
| 8798 | `visit_Subscript` | `if (` |
| 8886 | `visit_Subscript` | `if arr in _strat_hist:` |
| 9036 | `_case_value_expr` | `if isinstance(stmt, ast.Expr):` |
| 9074 | `visit_Switch` | `if pat is None:` |
| 9228 | `_coerce_if_assign_val` | `if self._is_safe_numeric_expr(val):` |
| 9297 | `_emit_switch_assign` | `if node.orelse:` |
| 9546 | `visit_FunctionDef` | `if getattr(node, "export", None) or getattr(node, "method", None):` |
| 9723 | `visit_FunctionDef` | `if self._func_body_returns_udt(last_ast):` |
| 9833 | `visit_FunctionDef` | `if needs_drawings:` |
| 9899 | `visit_FunctionDef` | `if not self.object_mode:` |
| 9905 | `visit_FunctionDef` | `if needs_strategy:` |
| 10428 | `visit_ForIn` | `if added_scalar:` |

