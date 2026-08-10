# AGENT 02 — AST Evaluator Core Audit

**Date:** 2026-08-10 
**Scope:** Execution engine without full builtins deep-dive 
**Mode:** Read-only 
**Auditor role:** Senior code audit of interpreter core 

**Focus paths:**

| Path | Role |
| --- | --- |
| `src/pynescript/ast/evaluator/base.py` | Context, constants, registries, bar-loop caches |
| `src/pynescript/ast/evaluator/expressions.py` | Ops, compare, call dispatch, if/switch expr |
| `src/pynescript/ast/evaluator/statements.py` | Script body, assign/var, loops, UDF, import |
| `src/pynescript/ast/evaluator/series_buffer.py` | Chronological ring / `RingPineSeries` |
| `src/pynescript/ast/evaluator/names.py` | Name / Attribute / Subscript |
| `src/pynescript/ast/evaluator/literals.py` | Constant / Tuple |
| `src/pynescript/ast/evaluator/events.py` | StrategyEvent dataclass |
| `src/pynescript/ast/evaluator/types.py` | EvaluatorProtocol |
| `src/pynescript/ast/evaluator/libraries.py` | LibraryModule / registry / stubs |
| `src/pynescript/ast/evaluator/__init__.py` | NodeLiteralEvaluator composition |
| `backend/runtime.py` | Host bar loop (glance) |

---

## Executive summary

The evaluator core is a **mature, performance-hardened bar-mode interpreter**: mixin MRO, AST call-site caching, arg plans, dual series storage, dual-namespace UDFs, and careful Pine `na`/`switch`/`history` semantics. It has clearly absorbed multiple parity and perf rounds (switch-na, UDF call-site series, same-bar `set_current`, `_pine_defs_locked`).

**Biggest residual risks are semantic, not structural:**

1. **`var` and `varip` are identical** at the assignment layer (init-once only).
2. **`AugAssign` / tuple unpack bypass `_bind_series_name`**, so history-tracked locals can lose series identity mid-bar.
3. **Dual history layouts** (host lists chronological; `PineSeries` newest-first; optional ring) force reverse/copy paths and array-method recovery that can allocate or mis-order.
4. **Soft-fail culture** (unresolved names → bare strings; missing libs → chainable stubs; many `except Exception`) keeps corpus green but can **mask real bugs** as `na`.
5. **Default mock `bid`/`ask`** (`100.01` / `100.02`) can silently drive tick scripts when the host omits quotes.

Overall engineering quality is **high for an interpreter this large**; correctness debt is concentrated in Pine edge semantics and a few mutation paths that skipped the series-binding funnel.

**Headline quality score: 7.5 / 10** (core design 8+, residual semantics / dual-buffer debt pulls down).

---

## Critical findings

### C1 — `var` / `varip` collapsed to the same init-once path

**Severity:** Critical (realtime / intrabar parity) 
**Where:** `statements.py:722–735`

```722:735:src/pynescript/ast/evaluator/statements.py
 # -- Handle var / varip: initialize once (first time declaration runs) --
 # Pine ``var`` is not strictly bar_index==0: a ``var`` inside
 # ``if barstate.islast`` or a function body must init on first
 # *execution* of that declaration, which may be a later bar.
 if isinstance(mode, (ast.Var, ast.VarIp)):
 if isinstance(node.target, ast.Name):
 name: str = node.target.id # type: ignore[attr-defined]
 declared: set[str] = self._var_declarations # type: ignore[attr-defined]
 if name not in declared:
 if node.value:
 value = self.visit(node.value) # type: ignore[attr-defined]
 self._bind_series_name(name, value)
 declared.add(name)
 return
```

**Issue:** the reference platform `varip` re-initializes / updates on **intrabar** realtime ticks for the *same* `bar_index`, while `var` does not. Here both modes only run the RHS the first time the declaration is executed, then permanently skip. UDT fields record a `varip` flag (`statements.py:1016–1026`) but assignment does not consult it.

**Impact:** Strategies / indicators that rely on `varip` under `barstate.isrealtime` will diverge from reference; historical bar-by-bar Runtime (`barstate.isrealtime = False` in `backend/runtime.py:1179`) may hide this until live hosts exist.

**Recommendation:** Track init by `(name, bar_index)` vs permanent set; on realtime tick for `varip`, re-run initializer or mark dirty per host contract. Document intentional gap if only historical mode is supported.

---

### C2 — `AugAssign` overwrites series wrappers with scalars (history lost)

**Severity:** Critical when `name ∈ _history_names` or value is already `PineSeries` 
**Where:** `statements.py:965–980`

```965:980:src/pynescript/ast/evaluator/statements.py
 if isinstance(node.target, ast.Name):
 var_name = node.target.id
 ctx = self.context # type: ignore[attr-defined]
 if var_name in ctx:
 current = ctx[var_name]
 rhs = self.visit(node.value) # type: ignore[attr-defined]
 from pynescript.ast.evaluator.expressions import (
 _BINOP_RAW,
 _elementwise_binary,
 )

 raw = _BINOP_RAW.get(type(node.op))
 if raw is not None:
 ctx[var_name] = _elementwise_binary(raw, current, rhs)
 return
```

**Issue:** `_elementwise_binary` / `_as_scalar_operand` unwrap `PineSeries` / ring wrappers to `.current` and return a bare `float`/`int`. That result is stored **directly** into `context`, bypassing `_bind_series_name` / `set_current`. After `x += 1`, `x[1]` no longer has a history buffer (scalar subscript path → offset>0 → `na`).

**Evidence contrast:** `visit_ReAssign` and plain `visit_Assign` correctly call `_bind_series_name` (`statements.py:703`, `870`).

**Recommendation:** Always funnel name targets through `_bind_series_name(var_name, _elementwise_binary(...))` after unwrapping operands, not after discarding the wrapper.

---

## High findings

### H1 — Tuple unpack skips series history binding

**Severity:** High 
**Where:** `statements.py:760–809`, especially `804–805`

```804:805:src/pynescript/ast/evaluator/statements.py
 if isinstance(target_node, ast.Name):
 self.context[target_node.id] = val
```

**Issue:** Multi-assign (`[a, b] = …`) writes raw values into `context`. If a name is later / also used as `a[1]`, history was collected in `_history_names`, but this path never creates/updates a series. `ReAssign`/`Assign` of the same name would track; unpack will not.

**Recommendation:** Use `_bind_series_name` for each Name elt (or a shared helper used by Assign, ReAssign, unpack).

---

### H2 — Unresolved identifiers become bare strings, not `na`

**Severity:** High (silent type pollution) 
**Where:** `names.py:191–199`; arg plans mirror this (`expressions.py:910–917`, `963–971`)

```191:199:src/pynescript/ast/evaluator/names.py
 try:
 return self.context[name]
 except KeyError:
 pass
 if name in _BARE_SERIES_BUILTINS and self._is_registered_builtin(name):
 return self._call_builtin(name, [])
 # Return the name as a string if not in context - allows for lazy evaluation
 return name
```

**Issue:** Missing locals resolve to the **identifier string**. Soft `+` concat then produces strings (`"x" + 1`-style), comparisons / truthiness behave non-`na`, and overload receivers can mis-tag as `string`. `_normalize_na` only special-cases the strings `"na"` / `"nan"` / `"none"` (`statements.py:137–149`), not arbitrary ids.

**Mitigating note:** Call soft-fail intentionally avoids “Unknown built-in” for demo helpers (`expressions.py:766–783`) — good for corpus, bad for hard failures.

**Recommendation:** Prefer `None` for free-value contexts; keep lazy strings only for *call* callees / qualified builtin recovery. Or gate with a debug flag that raises on unbound reads.

---

### H3 — Dual series layouts + array recovery reverse-copy thrash

**Severity:** High (correctness + perf) 
**Where:**

- `names.py:292–302` (array method recovery reverses `history`)
- `series_buffer.py` module doc + dual path (`PYNE_SERIES_RING` default off)
- Runtime dual storage: `PineSeries` + chronological `current_series` lists (`backend/runtime.py:1058–1071`, `1241–1248`)

```292:302:src/pynescript/ast/evaluator/names.py
 if not isinstance(receiver, list) and hasattr(value, "history"):
 hist = getattr(value, "history", None)
 if isinstance(hist, list):
 # history is most-recent-first; reverse for chronological array
 try:
 receiver = list(reversed(hist))
 except Exception:
 receiver = value
```

**Issues:**

1. **Semantic:** `NewestFirstHistoryView` is not a `list`, so ring series may not take this recovery path; legacy `PineSeries.history` is a `deque` — also **not** `isinstance(hist, list)`, so recovery may fail to treat series as array receivers.
2. **Perf:** When it *does* reverse a list, every `series.arrayMethod()` allocates a full reverse copy.
3. **Architecture:** Two truth sources for OHLCV (wrapper + host list) is intentional but fragile; comments in `series_buffer.py:32–39` acknowledge this as status quo.

**Recommendation:** Single chronological buffer as source of truth; newest-first only as a view. Array methods should take chronological views without full reverse when possible. Fix `isinstance(hist, list)` to accept `Sequence` / duck history.

---

### H4 — Mock default `bid` / `ask` in global constants

**Severity:** High for tick / 1T scripts without host quotes 
**Where:** `base.py:48–50`, injected via `setdefault` at `base.py:210–211`

```48:50:src/pynescript/ast/evaluator/base.py
 # v6 feature (February 2025): bid and ask variables on 1T timeframe
 "bid": 100.01, # Mock bid price for 1T timeframe
 "ask": 100.02, # Mock ask price for 1T timeframe
```

**Issue:** Hosts that never set `bid`/`ask` still expose **realistic-looking** prices. Runtime only patches bid/ask when OHLCV bars contain those keys (`backend/runtime.py:1275–1280`). Scripts computing spreads / ticks get a constant 0.01 spread forever.

**Recommendation:** Default to `None` (na) unless the host injects; keep mocks only under an explicit test/fixture path.

---

### H5 — Silent loop cap at 1_000_000 iterations

**Severity:** High (silent wrong results) 
**Where:** `statements.py:1147–1148`, `1232–1233`, `1269–1287`

**Issue:** `while` / `for` stop after 1e6 iters **without** raising. Pine-like runtime errors (`"loop is too long"`) are not surfaced. Nested corpus demos may “finish” with partial work.

**Recommendation:** Raise a dedicated `RuntimeError` / Pine-style error when the cap is hit (or set a host-visible flag). Matching soft-fail policy for indicators is a product choice — document it.

---

### H6 — Import soft-stubs swallow missing libraries

**Severity:** High (correctness opacity) 
**Where:** `statements.py:1711–1787`

**Issue:** Unknown `import namespace/name/version` installs a chainable stub that returns self / 0 / None. Scripts continue with empty pivots, zero sizes, no-op methods. A warning is best-effort (`log_warning` in try/except). `_import_stubs` list is good host telemetry **if** the host checks it.

**Recommendation:** Keep stubs for corpus, but surface hard-fail mode (`PYNE_STRICT_IMPORT=1`) and ensure Runtime always attaches `_import_stubs` to the response payload (verify host, out of core scope).

---

## Medium findings

### M1 — `_call_site_cache` allocated but unused

**Severity:** Medium (dead / confusing state) 
**Where:** `base.py:223–225`

```223:225:src/pynescript/ast/evaluator/base.py
 # Bar-loop call-site caches (pre-allocated so visit_Call avoids None checks).
 # Keyed by id(Call AST node); AST is stable for the script lifetime.
 self._call_site_cache: dict[int, tuple] = {}
```

**Actual mechanism:** Sites attach to the AST via `_pine_call_site` (`expressions.py:100–106`, `640–643`) — correctly avoiding `id()` reuse bugs (commented at `635–639`). The dict on `BaseEvaluator` is leftover noise.

**Recommendation:** Remove `_call_site_cache` or document as deprecated; prefer one story.

---

### M2 — Call-expression history keyed by `id(Call)` still used for history buffer

**Severity:** Medium 
**Where:** `names.py:451–498`

**Issue:** Site cache for *dispatch* moved off `id()`; **call-expression history** (`time(...)[1]`, `ta.change(x)[1]`) still uses `id(value_node)` as dict key. Safe while AST is long-lived (Runtime parses once). Unit tests that re-parse every bar or reconstruct Call nodes will scramble history. Same class of bug the call-site cache fixed.

**Recommendation:** Attach history handle on the Call node (`_pine_call_hist`) like `_pine_call_site`.

---

### M3 — UDT method invoke path weaker than free UDF path

**Severity:** Medium 
**Where:** `expressions.py:_invoke_method` (`1323–1400`) vs `statements.py` `user_function` (`1432–1540`)

**Gaps vs free UDFs:**

- No per-call-site series-local isolation (`_udf_call_site_state` / `_pine_udf_site`).
- No body plan / Assign-as-return special case for trailing `Assign`/`ReAssign` (UDF path treats assign results as return; method body only updates `result` on `ast.Expr`).
- Defaults for unbound params use `param.name not in saved` (works) but series locals inside methods remain shared on the live `context`.

**Impact:** `method foo(Type this)` with internal `x[1]` state across multiple instances / call sites can cross-talk.

---

### M4 — History-name collection only sees `Name` subscript bases

**Severity:** Medium 
**Where:** `statements.py:434–445`

Only `Subscript` whose `value` is `ast.Name` is collected. Patterns like `(expr)[1]` or only attribute paths do not mark assign targets. Acceptable for classic Pine locals, incomplete for fancy forms.

Also: scan runs once per script (`_history_names_scanned`); dynamic codegen is N/A, but nested `FunctionDef` series locals are re-collected separately — good (`statements.py:1421–1424`).

---

### M5 — Broad `except Exception` soft-fails in hot paths

**Severity:** Medium 
**Where (core only):**

| File | Lines (approx) |
| --- | --- |
| `expressions.py` | 186–187 (`_switch_case_matches`), 242–243 (soft concat) |
| `names.py` | 301–302, 472–474, 497–498, 615–617 |
| `statements.py` | 192–193, 399–400, 523–525, 579–581, 922–926, 1785–1788 |

**Positive:** Some paths distinguish callee-body `TypeError` via `_type_error_from_callee` (`expressions.py:51–60`) and re-raise — excellent fail-closed design.

**Negative:** Remaining bare `except Exception` can hide programming errors (especially series construction / hist reverse). Prefer `(TypeError, ValueError, AttributeError)`.

---

### M6 — `BoolOp` / `if` use Python truthiness, not Pine three-valued logic

**Severity:** Medium (known / partially intentional) 
**Where:** `expressions.py:404–413`, `451–465`, `1450–1465`

- `and`/`or` return Python `bool`, short-circuiting with `not visit(value)`.
- `None` is falsy → `and`/`or` treat `na` as false (documented).
- Unary `not na` propagates `na` (`expressions.py:498–500`) — **inconsistent** with `BoolOp`/`if` where `na` is plain false.

**Impact:** `if na` vs `not na` diverge from full Pine three-valued expectations in some edge scripts.

---

### M7 — Soft string concat and list element-wise ops are easy to over-apply

**Severity:** Medium 
**Where:** `expressions.py:232–270`

`"x" + 1` and list/series broadcast are corpus-friendly. Risk: accidental string pollution from H2 turns numeric expressions into concat without error.

---

### M8 — `_PURE_CONST_FOLD_BUILTINS` only folds `timestamp`

**Severity:** Medium / Low (missed perf, not wrong) 
**Where:** `expressions.py:90–94`

Only `timestamp` is folded when all args are literals. Other pure helpers (`math.*` constants, static color math) still re-run every nested-loop iteration. Intentional narrowness is fine; room to expand carefully.

---

### M9 — `RingPineSeries` not in `_SERIES_TYPE_NAMES` frozensets

**Severity:** Medium-Low 
**Where:** `expressions.py:68`, `statements.py:118`

```68:68:src/pynescript/ast/evaluator/expressions.py
_SERIES_TYPE_NAMES = frozenset({"PineSeries", "_SeriesResult"})
```

Duck-type path (`current` + `history`) still unwraps ring series. Fine today; fragile if a wrapper has `current` without wanting scalar unwrap.

---

### M10 — `var` inside locked defs / first-bar lock interaction

**Severity:** Medium 
**Where:** Host locks after first bar (`backend/runtime.py:1345–1349`); `visit_FunctionDef` no-ops when locked.

**Issue:** Functions defined only after bar 0 (unusual) would never register. Normal scripts define at top level on bar 0 — OK. Conditional `import` after bar 0 also skipped (`visit_Import` respects lock). Document host contract: all defs must execute on first `visit(Script)`.

---

## Low findings

### L1 — `base.py` constant table is large but flat-string keyed

Colors, shapes, timeframe flags, dayofweek, etc. live as dotted string keys in one dict. Clear and host-overridable via `setdefault`. Tradeoff: no nested namespace objects unless host injects them (`syminfo`, `timeframe` objects in Runtime).

### L2 — `generic_visit` raises `ValueError` with type only

`base.py:237–247` — no lineno / node dump. Harder bar-loop diagnostics than Runtime’s wrapper messages.

### L3 — `events.py` is clean but incomplete surface

Only strategy order kinds; no alert events here (alerts live under builtins). Frozen dataclass + manual `to_dict` is good for drain perf.

### L4 — `types.py` protocol incomplete vs real surface

Protocol documents `visit`, `_error`, `_call_builtin`, `_invoke_method`, `_handle_udt_new`. Mixins also use `_is_registered_builtin`, `_user_functions`, `_strategy_state`, etc., via duck typing. Fine for optional Protocol; static checkers get partial help.

### L5 — `literals.visit_Tuple` returns **list**

Documented Pine dynamic sequences (`literals.py:59–70`). Callers must not assume immutability.

### L6 — Dead / redundant enum store

`statements.py:1124–1126` assigns `enum_name` twice to the same dict (no-op duplicate).

### L7 — Exception classes for break/continue

`BreakLoop` / `ContinueLoop` as control flow is Pythonic and clear; only cost is exception overhead in tight loops (acceptable vs flags for rare break).

### L8 — Library stub known exports limited

`libraries.py:STUB_KNOWN_EXPORTS` only index flatten helpers. Fine as opt-in polyfill.

---

## Documentation audit

| Area | Assessment |
| --- | --- |
| Package `__init__.py` | **Excellent** — MRO diagram, host contract, na/series/var semantics, strategy events |
| Module docstrings (`expressions`, `names`, `statements`, `series_buffer`, `events`, `libraries`) | **Strong** — Pine indexing, dual storage, call-site cache history, parity notes |
| Hot-path comments | **Very good** — explain *why* (id reuse, dual namespace, set_current same-bar, O(bars²) lock) |
| Method docstrings | **Generally present** on public `visit_*`; helpers often documented |
| Protocol (`types.py`) | Thin but intentional |
| Gaps | `varip` documented as init-once **without** reference realtime distinction; dual buffer complexity needs a single architecture doc (partially in `series_buffer` + `backend/series.py`); soft-fail policy not centralized |

**Doc quality score: 8.5 / 10** for core modules — better than average OSS interpreters.

---

## Modernization & performance-aware patterns

### Already in place (strengths)

1. **AST-attached call-site cache** + arg-plan opcodes (`_AP_NAME` / `_AP_CONST` / unrolled 1–3 arg shapes).
2. **Type-identity fast paths** (`type(x) is float`) for bar-mode BinOp/Compare.
3. **Raw op tables** skipping wrapper frames (`_BINOP_RAW` + `_elementwise_binary`).
4. **Static for-to** → Python `range` when bounds are Constant.
5. **Dual-namespace UDFs** (`_user_functions`) so series can reuse function names.
6. **Per-UDF-call-site series state** (`_udf_call_site_state`, `_pine_udf_site`).
7. **Same-bar series rewrite** via `set_current` (ring + legacy).
8. **`_pine_defs_locked`** after first bar — critical host contract.
9. **Optional chronological ring** (`PYNE_SERIES_RING`) with API-compatible wrapper.
10. **Fail-closed body TypeError** detection via traceback depth.

### Opportunities

| Idea | Benefit | Risk |
| --- | --- | --- |
| Unify series storage (chrono ring default) | Kill reverse thrash; simpler `_as_series` | Migration; TA helpers |
| Specialize bytecode / threaded interpreter for hot Script bodies | Multi-x bar loop | Large project |
| Expand pure-fold set carefully | Nested-loop demos | Side effects |
| Slot-based context for OHLCV keys | Fewer dict probes | Host flexibility |
| Structured errors with lineno from AST | UX | Slight overhead |
| Strict mode flag for unbound names / imports | Correctness for prod | Corpus noise |
| Wire AugAssign + unpack through `_bind_series_name` | Correctness | Small |

---

## Quality scorecard

| Dimension | Score (1–10) | Notes |
| --- | --- | --- |
| Correctness (historical bar mode) | 8 | Strong na/switch/history work; varip & AugAssign gaps |
| Correctness (realtime / varip) | 4 | varip ≈ var |
| Performance awareness | 9 | Extensive hot-path engineering |
| Design clarity | 7 | Mixins clear; dual series + soft-fail culture add cognitive load |
| Error handling | 6.5 | Good fail-closed for body TypeError; many soft na paths |
| Documentation | 8.5 | Module/host docs excellent |
| Testability | 8 | Host lock, series flags, pure fold — need flags for strict mode |
| Maintainability | 7 | Large statements/expressions files; well-commented |
| **Overall** | **7.5** | Production-capable interpreter with known semantic debt |

---

## Prioritized recommendations

### P0 — Correctness

1. **Route `AugAssign` through `_bind_series_name`** (`statements.py:965–980`). Add unit: history-tracked `x += 1` preserves `x[1]`.
2. **Route tuple unpack through `_bind_series_name`** (`statements.py:804–805`).
3. **Implement or explicitly refuse `varip` realtime semantics**; if refuse, document in `__init__.py` / runtime guide and consider raising if `barstate.isrealtime` and script contains `varip`.
4. **Default `bid`/`ask` to `None`** in `_MATH_CONSTANTS` (`base.py:48–50`).

### P1 — Robustness

5. **Unbound free values → `None`**, keep string lazy only for call resolution.
6. **Raise on loop iteration cap** (or host-visible counter).
7. **Strict import mode** + always expose `_import_stubs` from Runtime responses.
8. **Attach call-expression history on the Call AST node**, not `id()`.
9. **Align UDT `_invoke_method` series-local / return conventions** with free UDFs.

### P2 — Architecture / perf

10. **Finish ring-buffer migration** as default; retire dual reverse paths in TA/array recovery.
11. **Remove dead `_call_site_cache`**.
12. **Narrow `except Exception`** to expected types on hot paths.
13. **Expand pure const-fold** only with a proven side-effect-free allowlist.

### P3 — Docs / quality

14. Single **“Series indexing contract”** doc (list chrono vs PineSeries newest-first vs ring) linked from `names` / `series_buffer` / Runtime.
15. Document soft-fail matrix (unbound name, missing import, non-callable, loop cap, signature TypeError).
16. Split `statements.py` (~1900 lines) into assign/series, control-flow, defs/import modules when next large feature lands.

---

## Host integration notes (Runtime glance)

From `backend/runtime.py` bar loop (approx. 1192–1357):

- Host mutates **the same** `context` dict each bar (`bar_index`, series updates) — matches UDF rebind design.
- Injects chronological `evaluator.current_series` for TA; series wrappers updated via `.update`.
- `visit(tree)` once per bar; `_pine_defs_locked = True` after first bar.
- Strategy events drained per bar; plots reset/finish around visit.
- Fail-closed on bar exceptions (returns error payload) — good complement to evaluator soft-fails.

Evaluator core and Runtime are **tightly coupled by convention** (`_pine_defs_locked`, `_var_declarations` reset, series caps). Breaking those without host updates is a silent multi-bar bug class.

---

## Evidence index (grep / method)

| Pattern | Core result |
| --- | --- |
| `TODO` / `FIXME` | None in core evaluator files (clean) |
| `except Exception` | Present in statements/names/expressions (listed above) |
| Mutable defaults | LibraryModule `exports` uses `field(default_factory=dict)` — correct |
| Call-site design | AST attribute preferred; leftover id-keyed history buffer remains |
| Soft-fail | Intentional corpus strategy; needs strict mode for production |

---

## Conclusion

The evaluator core is **battle-hardened and well-documented**, with sophisticated Pine-facing fixes (switch-na, dual namespace, same-bar series, UDF call-site isolation, defs lock). The main audit message is not “rewrite,” but **close the mutation funnel** (`_bind_series_name` for all name writes), **stop pretending varip works**, **fail honest on mocks/stubs/unbound names when strict**, and **finish series storage unification** so history indexing stops being a multi-representation minefield.

**Next audit handoff:** builtins (especially `technical`, `strategy`, `request`) build on these contracts; series thrash and soft-fail policies here amplify TA and broker bugs there.
