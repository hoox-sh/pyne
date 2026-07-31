# AGENT 05 — Compiler language surface coverage

**AGENT_ID:** 05  
**ROLE:** Compiler language surface (control flow, strings, inputs, chart, math)  
**BASE_SHA:** `32697c97f7e56de817325356e4dbd692809ecbe8`  
**Date:** 2026-07-31  

## 1. Scope & files

| File | Change |
|------|--------|
| `src/pynescript/compiler/compiler.py` | Safer `_is_safe_numeric_expr`; chart viewport times; math/timestamp stubs stay numeric; materialize ignores loop-counter scalars |
| `tests/test_compiler_numba.py` | `TestLanguageSurfaceNumeric` (6 cases) |
| `docs/perf_round6/AGENT_05_compiler_surface.md` | This report |

**Owns (not Agent 04):** visitor control-flow / surface — not TA kernel bodies.

## 2. Bugs found

| Sev | Bug | Status |
|-----|-----|--------|
| **High** | `_is_safe_numeric_expr` rejected any expr containing `[` (history / series load), so `plot(ta.sma(close,a)*b)`, `for i … s := s + close[i]`, etc. flipped **object_mode** and wrapped stores in `safe_float` even though the IR was njit-legal | **Fixed** |
| **High** | `math.tanh/sinh/cosh` always emitted `safe_float(...)` (pure Python) → nopython warm thrash / object path | **Fixed** |
| **Med** | `math.todegrees` / `toradians` always used `safe_float` → same thrash | **Fixed** (safe only when arg unsafe) |
| **Med** | `math.random` stub forced `object_mode` for whole script (constant `0.5`) | **Fixed** |
| **Med** | `timestamp(...)` stub forced object mode (`0`) | **Fixed** → `0.0` numeric |
| **Med** | `chart.left/right_visible_bar_time` both `0.0` (R5 P2 residual) | **Fixed** right → last-bar synthetic time |
| **Low** | Disk/IR compile cache can serve **stale object_mode** IR for the same source after emitter improvements (tests use `use_cache=False`; clear disk cache after compiler changes) | Documented |

## 3. Changes

### 3.1 `_is_safe_numeric_expr` (main lever)

- Accept compound arithmetic of series loads, history ternaries, `numba_*` / `np.*` calls.
- Strip balanced `name_arr[...]` via `_strip_series_index_loads`.
- Treat ternary keywords (`if`/`and`/…) as non-calls; match `np.tanh` as one callee.
- Still reject strings, UDT walrus binds, `safe_float` / `udt_*` / UDF calls, string/UDT series buffers.

### 3.2 Chart viewport (R5 P2)

Align with compile `time` model (`bar_index * 60000` ms):

- `chart.left_visible_bar_time` → `0.0` (first bar)
- `chart.right_visible_bar_time` → `(float(n_bars - 1) * 60000.0)` (last bar, equals bare `time` on last bar)

No OHLCV time array is threaded into `execute_script_compiled` yet; synthetic series is the consistent nopython default (interpret Runtime still seeds real bar times).

### 3.3 Math / timestamp surface

| Construct | Before | After |
|-----------|--------|-------|
| `math.random` | object_mode + `0.5` | numeric `0.5` |
| `math.tanh/sinh/cosh` | `np.*(safe_float(x))` | `np.*(x)` like cos/sin |
| `math.todegrees/toradians` | always `safe_float` | bare when arg safe |
| `timestamp(...)` | object_mode + `0` | numeric `0.0` stub |

### 3.4 Materialize / script end

- Loop counters in `scalar_vars` no longer force `store_src_py` or end-of-script object_mode by themselves (`scalar_vars - loop_counters`).

## 4. Benchmarks

No full `bench_pipeline` claim (correctness/coverage agent). Structural win: scripts that previously emitted object-mode bar loops for pure numeric surface (for-loops, input*SMA, math.random) now take `@numba.njit` path — same order of magnitude as other numeric compile scripts once warm.

Spot checks (n=30, `use_cache=False`):

| Script | object_mode before | after |
|--------|--------------------|-------|
| `for i … close[i]` sum | True | **False** |
| `input.int` + `sma*float` | True | **False** |
| `math.random` + `math.sum` | True | **False** |
| `math.todegrees(pi)` | True | **False** |
| chart L/R viewport | False (but R=0) | **False**, R=last time |

## 5. Tests run

```bash
# clear stale disk IR after emitter changes
PYTHONPATH=src:. .venv/bin/python -c \
  "from pynescript.compiler.engine import clear_compile_cache, clear_disk_compile_cache; \
   clear_compile_cache(); clear_disk_compile_cache()"

PYTHONPATH=src:. .venv/bin/python -m pytest \
  tests/test_compiler_numba.py tests/test_compiler_objects.py -q --tb=line
# → 198 passed
```

New: `TestLanguageSurfaceNumeric` (viewport, for-loop, input×sma, math/timestamp, string-input regression).

## 6. Residual `force_object` / object_mode reasons

Still **correctly** force object mode (do not “fix” these):

| Category | Examples | Why |
|----------|----------|-----|
| **String / color series** | `input.string`, `input.color`, `input.session`, `str.*`, bare color names | pyobject / unicode — njit refuses |
| **Collections** | `array.*`, `map.*`, `matrix.*` | Python lists/dicts |
| **UDT / chart.point** | `type` defs, field reads, `chart.point.from_index` | dict handles |
| **Drawings / tables** | `label/line/box/table/polyline.*` | `__drawings` events |
| **Strategy broker** | `strategy()`, entries/exits | side effects + broker state |
| **Library import** | `import … as` | unknown methods stubbed |
| **True object scalars** | map handles, drawing ids residual in `scalar_vars` | not float64 series |
| **Engine recovery** | `force_object_mode=True` after nopython TypingError | structural fallback |
| **Unknown calls** | external lib methods | stub `None` + object |

Still **weak / stub** but no longer force object by themselves:

| Construct | Behavior |
|-----------|----------|
| `math.random` | constant `0.5` (deterministic) |
| `timestamp(...)` | `0.0` |
| `chart.*` colors / mode flags | fixed defaults |
| `time` / viewport | synthetic 60s bars, not host ms |

## 7. Residual risks / out of scope

- **No real time array** in compile signature — viewport/time still synthetic; wiring host `time` into `execute_script_compiled` is a future engine+visitor change.
- **Disk cache staleness** after emitter upgrades: clear `clear_disk_compile_cache()` or bump meta version (Agent 06 territory).
- **TA stubs** (dmi/supertrend/alma/percentrank real kernels) → Agent 04.
- **While-loop counters as series** (`i = 0` then `while`) still use `i_arr` (series semantics); numeric path works if stores stay safe-numeric, but not as lean as for-counter locals.
- **string concat / color** correctly stay object — not optimized further.

## Handoff summary (≤20 lines)

See agent message.
