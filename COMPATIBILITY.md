# Compatibility — PYNE / PyneTS / pyne-worker / pine-worker

**hoox-pyne 0.3.10** · import `pynescript` · CLIs `pyne` / `pyne-lsp`

PYNE aims for **high syntactic fidelity** and **strong semantic compatibility** with
Pine Script™ v5/v6 on the language core (parser, AST round-trip, builtins, strategy
primitives). It does **not** claim:

- official TradingView® certification or endorsement
- complete platform identity (chart host, proprietary data, editor-only UI)
- bit-identical results vs the TradingView® platform on every script or bar

Product wording: [compatibility](https://hoox.sh/pyne/docs/reference/compatibility).

---

## Implementations

| | **PYNE** (`pynescript`) | **PyneTS** | **pyne-worker** | **pine-worker** |
|---|---|---|---|---|
| Role | Language SoT | TS / Bun **library** | Python CF isolate | Legacy TS CF Worker |
| Repo | this repo | [hoox-sh/pynets](https://github.com/hoox-sh/pynets) (`pynets/` submodule) | [hoox-sh/pyne-worker](https://github.com/hoox-sh/pyne-worker) | [hoox-sh/pine-worker](https://github.com/hoox-sh/pine-worker) |
| In this checkout? | yes | submodule (may lag; pin is 0.1.0 interpret-only) | no | **no** |
| Public API | `parse` / `unparse` / `Runtime.run` | same names | `POST /run` (vendors Python Runtime) | own `/run` + trade-forward |
| Oracle | — | Python wins | Python (thin wrap) | Python when compared |

`pine-worker/` is **not** colocated. New TypeScript library work belongs in PyneTS.

---

## Corpus snapshot (set01–04 · local · 2026-08-09)

2477 open-source scripts; **not shipped** in git.

| Suite | Rate |
| --- | ---: |
| Parse + unparse | **99.96%** (2476 / 2477) |
| Runtime interpret | **100%** excl. EXPECTED_FAIL (2466 OK + 11 intentional demos) |
| set01 Runtime | **249 / 249** |

Not TradingView® platform parity. EXPECTED_FAIL paths are listed intentional demos
(`runtime.error` guards, lower-TF security, pathological loops).

---

## Dual-host (interpret ↔ compile)

Same script + OHLCV under `Runtime.run(..., mode="interpret")` and `mode="compile"`;
series compared with nan-aware allclose.

- Harness: `scripts/compare_interp_compile.py`
- Smoke: `tests/test_interp_compile_parity.py`

Foreign / complex `request.security` → `na` on both backends when no feed (no invented
chart-close-as-foreign). Structural `hline` / `fill` key sets may differ by design.

---

## Roadmap residuals (0.3.10)

| ID | Status |
| --- | --- |
| **H1** package Runtime SoT | ✅ largely done (`pynescript.runtime`; `backend.runtime` shim) |
| **H2** warm compile | ✅ |
| **C1** corpus Runtime | ✅ 2026-08-09 |
| **T1** series caps | ✅ `PYNE_SERIES_CAP` default ON |
| **T2** incremental TA | ✅ through volume `obv`/`wad`/`cmf`/`klinger`; leftover `nvi`/`pvi` |
| **F2** pending-fill | ✅ |
| **L2** webhooks | ✅ |
| **P1p** plot MISMATCH tail | ⚙️ harness landed |
| **F1** ATR/supertrend goldens | ⚙️ optional |

See `docs/ROADMAP.md` and `docs/pyne/reference/missing-features.mdx`.
