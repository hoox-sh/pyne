# pine-worker

TypeScript implementation of the Pine Script evaluator (parser + AST + runtime).

This is an **extra tool** of the main `pynescript` Python repository. It lives in this subdirectory so that:

- Parity fixtures and contracts (`tests/fixtures/parity/`) are co-located and easy to keep in sync.
- The ANTLR grammar remains the single source of truth (regenerate TS parser target from `../src/pynescript/ast/grammar/antlr4/resource/*.g4`).
- Development, testing, and porting can cross language boundaries in one checkout.

## Source of truth (SoT) boundary

**Python Runtime is SoT** (`pynescript.runtime` under `../src/pynescript/runtime/`).

| Layer | Role |
| --- | --- |
| `pynescript.runtime` (Python) | Public runtime SoT — series, host, evaluator semantics |
| `pine-worker` (this package) | **Experimental** TS worker / partial port — not a second SoT |

When semantics disagree, Python wins. This package should thin-wrap or align toward the Python contract rather than reimplement a full parallel Runtime.

**Series indexing matches Pine offsets** (same as Python `PineSeries` / TradingView):

- `series[0]` / `get(0, bar)` — current bar
- `series[1]` / `get(1, bar)` — previous bar (one bar ago)
- `series[n]` / `get(n, bar)` — `n` bars ago
- Negative history offsets → `na` (soft-fail, Python parity)

Do not invert polarity (positive is lookback into the past, not “future”).

## Status

This is the home of **Plan 2** of the strategy-events effort (see `../.opencode/plans/2026-07-05-pine-worker-strategy-events.md`).

Currently a skeleton + partial port of:

- AST Zod schemas + types (mirrors Python ASDL)
- Base evaluator + visitor dispatch
- PineSeries (historical bar access; Pine offset polarity)
- Core NA/loop signal semantics

Full builtins port, parser (ANTLR TS target), runtime loop, and strategy event emission are in progress. This is **not** a full Runtime reimplementation in TypeScript.

## Quick start (requires Bun)

```bash
cd pine-worker
bun install
bun test
bun run typecheck
```

## Parity with Python reference

The Python Runtime (`pynescript.runtime`) is the source of truth; see **Source of truth (SoT) boundary** above. Legacy `backend/` re-exports still exist for compatibility but public SoT lives under `src/pynescript/runtime/`.

Fixtures:

- `../tests/fixtures/parity/pine/*.pine`
- `../tests/fixtures/parity/json/*.json`

Run Python side to (re)generate:

```bash
python ../tests/fixtures/parity/generate_fixtures.py
```

TS parity harness will live under `test/parity/`.

## Converter / porting aid

A Python → TypeScript porting helper (skeleton generator) lives here:

```bash
python pine-worker/scripts/convert-python-to-ts.py \
  src/pynescript/ast/evaluator/builtins/numeric.py
```

It emits a `.ts` file with JSDoc + function signatures + TODO bodies to speed up the manual port while keeping you honest about parity.

It is intended to generate initial TS stubs/skeletons from Python builtin implementations to accelerate manual porting while preserving semantics.

## Relationship to hoox-setup / trade-worker

Once mature, `pine-worker` can be vendored or submoduled into hoox-setup as `workers/pine-worker` for the Cloudflare Worker packaging + service binding to trade-worker (Plan 3).

For now it is developed here as part of the pynescript monorepo-like layout.

## License

Same as parent pynescript project.
