# Launch post — PYNE (with AXIS + HOOX)

> Copy-paste body for Reddit. Title options live in
> [`publishing-plan.md`](./publishing-plan.md). 95% PYNE by design;
> AXIS/HOOX get one closing section. Trademark and risk disclaimers are
> part of the post — do not strip them.

---

Hi r/algotrading — I'm `jango_blockchained`, single author of a research
artifact I've been building in the open for the last year, and today the
whole stack is public: **PYNE**, an independent open toolchain for the
Pine Script™ language (v5–v6). `pip install hoox-pyne` — import package
`pynescript`, CLIs `pyne` / `pyne-lsp`. AGPL-3.0-only. No account, no
API key, no telemetry calling home.

The thesis, stated plainly: **if you cannot inspect the runtime, you
cannot trust the fill.** Pine Script™ strategies usually live and die
inside a closed host interpreter behind a subscription ceiling. PYNE
models the language as an inspectable pipeline instead:

```text
Source (.pyne / .pine)
  → ANTLR4 lexer / parser
  → ASDL AST  (parse → unparse round-trips)
  → bar-loop  (interpret | compile | auto)
  → plots · fills · drawings · strategy events · alerts
  → desk CLI / LSP / HTTP Pro API / edge workers / browser
```

Parse the language. Own the AST. That is the entire pitch.

## Abstract (such as it is)

PYNE is a from-grammar implementation of the Pine Script™ surface:
ANTLR4 grammars, ASDL-generated AST with visitor/transformer patterns,
a deterministic bar-loop evaluator with two engines (AST-walk
interpreter, Numba nopython compile path with object-mode fallback,
`mode=auto` to pick), plus the surfaces a toolchain needs to be useful
— a 14-command desk CLI, a real LSP server (`pyne-lsp`, ~940 builtins,
stdio, works in VS Code/Neovim/Zed/Emacs), an HTTP evaluation contract
(`POST /run` — script + OHLCV in, plots + events + alerts out), and
workers that are ports of the same engine rather than rewrites of the
language. Prefer `.pyne` for new work; keep `.pine` for
TradingView® exports.

## Results (local measurements, reproduced in CI)

Open-source regression corpus, sets 01–04 — 2,477 real-world scripts
(not shipped in git; the harness is):

| Suite | Rate |
| --- | ---: |
| Parse + unparse round-trip | **99.96%** (2,476/2,477 — the one residual is an intentional invalid-syntax demo) |
| Runtime interpret (50 bars) | **100%** excl. 11 intentional demos (`runtime.error` guards, lower-timeframe security, pathological loops) |

The hot loop got the full treatment in 0.5.0: slotted AST nodes (no
per-node `__dict__`), incremental TA kernels (SMA/EMA/RSI/BB, volume
kernels `obv`/`wad`/`cmf`/`klinger`/`nvi`/`pvi`, price kernels
`aroon`/`dpo`/`donchian`/`kst` — amortized O(1)/bar via monotonic
deques), unused-derived-series skip, warm Numba with disk IR cache and
prewarm. Same-machine interpret at 2,000 bars runs ~1.5–2.7× faster
than the naive walk depending on the script. Interpret↔compile plot
parity is verified by harness, not vibes.

## Threats to validity (read before you yell at me)

- This is **not** TradingView® platform parity and never claims to be.
  Known divergences are documented (`known_divergences.md`); the
  `request.security` policy, for example, is deliberately conservative
  (same-symbol simple OHLCV, foreign/complex resolves to `na` — no
  invented foreign closes, ever).
- Coverage percentages are measurements of *my* corpus on *my*
  machine, not a certification of anything.
- Single author + AI assistance, built as a research artifact. Review
  the grammar and the runtime before trusting either with money —
  that's rather the point of shipping source.

## The honest limitations list

- Heavy research and warm Numba belong on the desk Pro API, not on a
  free-tier edge isolate (30s wall clock, 100 KB script, 100 K bars —
  physics is physics).
- `pyne-worker` (edge `POST /run` on Cloudflare® Workers) is the
  *wrap*, not the toolchain: no CLI, no LSP, no corpus harness. Those
  live in the main repo.
- No history ceilings in the engine, but *your* box still has RAM —
  series caps are on by default for a reason.

## It ships with siblings (the other 5%)

- **AXIS** (v2.6.1) — installable open charting PWA that runs PYNE
  three ways: local Pro API, Cloudflare® Worker, or fully offline in
  the browser via Pyodide. CEX OHLCV, drawings, on-chain TVL overlays,
  strategy reports, Tauri desktop shell.
- **HOOX** — the edge trading framework around it all
  (Cloudflare® Workers mesh, trade routing, alert webhooks). PYNE is
  its language engine; everything else composes around it.

Links: engine → <https://github.com/hoox-sh/pyne> ·
docs → <https://hoox.sh/pyne/docs> ·
charting → <https://github.com/hoox-sh/axis> ·
framework → <https://hoox.sh>

Happy to answer anything — grammar design, why ASDL, the incremental-TA
trickery, or where the bodies are buried in `ta.*`. Hardest questions
get the best answers.

---

*Disclaimers (please read):*
*Pine Script™ and TradingView® are trademarks of TradingView, Inc.
Cloudflare® is a registered trademark of Cloudflare, Inc. Workers AI™
is a trademark of Cloudflare, Inc. PYNE, AXIS, and HOOX are independent,
unofficial open-source projects — not affiliated with, authorized by,
sponsored by, or endorsed by TradingView, Inc. or Cloudflare, Inc. Not
official TradingView® products, services, or platform substitutes, and
no substitute for a hosted platform account. Language references are for
interoperability/compatibility documentation only; nothing here
redistributes proprietary TradingView® platform software, charting UI,
or closed data services.*
*Risk: algorithmic trading involves substantial risk of loss, including
total loss. Past performance — mine, yours, or a backtest's — is not
indicative of future results. Paper-trade before real funds; start
small; assume every bug is yours until proven otherwise. The authors
accept no liability for financial losses. This is a research artifact,
not financial advice.*
