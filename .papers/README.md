# PYNE Academic Paper Series (arXiv-ready LaTeX)

Full academic-grade manuscripts describing the **PYNE** (`pynescript` / `hoox-pyne`) open toolchain for Pine Script™. Sources are structured for [arXiv](https://arxiv.org/) submission (`cs.PL`, `cs.SE`, `cs.PF`, `cs.CE`).

> **Pine Script™** and **TradingView®** are trademarks of TradingView, Inc.  
> PYNE is an **independent, unofficial** implementation and is not affiliated with, authorized by, sponsored by, or endorsed by TradingView, Inc.

## Series overview

| # | Directory | Title | Primary subjects |
|---|-----------|-------|------------------|
| 01 | [`paper01-architecture/`](paper01-architecture/) | **PYNE: An Open Dual-Engine Toolchain for Offline Pine Script Evaluation** | cs.PL, cs.SE |
| 02 | [`paper02-compiler/`](paper02-compiler/) | **Compiling Bar-Oriented Trading DSLs to Numba: Source-to-Source Lowering, Object-Mode Fallback, and Warm IR Caches** | cs.PL |
| 03 | [`paper03-series-runtime/`](paper03-series-runtime/) | **Efficient Series History and Incremental Technical Analysis for Bar-Loop Interpreters** | cs.PF, cs.DS |
| 04 | [`paper04-grammar/`](paper04-grammar/) | **Formalizing a Charting DSL: ANTLR4 Grammar Engineering and ASDL Intermediate Representations for Pine Script** | cs.PL |
| 05 | [`paper05-parity-strategy/`](paper05-parity-strategy/) | **Numerical Parity and Strategy Semantics for Independent Pine Script Runtimes** | cs.CE, q-fin.CP |
| 06 | [`paper06-lsp-tooling/`](paper06-lsp-tooling/) | **Language Tooling for Financial DSLs: An LSP Architecture for Pine Script with Multi-Editor Delivery** | cs.SE |

Each paper is self-contained with abstract, introduction, technical body, evaluation, related work, limitations, conclusion, TikZ/pgfplots figures, algorithms, and bibliography.

## Layout

```text
.papers/
├── README.md                 # this file
├── Makefile                  # build all / clean
├── common/
│   ├── macros.tex            # shared packages, theorem envs, colors, listings
│   └── bibliography.bib      # shared BibTeX database
├── paper01-architecture/
│   ├── main.tex
│   ├── figures/              # TikZ figure inputs
│   └── main.pdf              # after build
├── paper02-compiler/
│   └── main.tex
├── paper03-series-runtime/
│   └── main.tex
├── paper04-grammar/
│   └── main.tex
├── paper05-parity-strategy/
│   └── main.tex
└── paper06-lsp-tooling/
    └── main.tex
```

## Build requirements

- **Preferred:** [Tectonic](https://tectonic-typesetting.github.io/) (pulls packages automatically)
- **Alternative:** TeX Live with `pdflatex`, `bibtex`, and packages: `amsmath`, `booktabs`, `tikz`, `pgfplots`, `natbib`, `hyperref`, `algorithm`, `listings`, `geometry`, `times`/`psnfss`, etc.

```bash
# From .papers/
make all          # pdflatex + bibtex for every paper
make paper02-compiler   # single paper
make clean        # aux files only
make distclean    # aux + PDFs
make check        # verify main.tex exists
```

With Tectonic (recommended on minimal hosts):

```bash
cd paper01-architecture && tectonic main.tex
# repeat for paper02–paper06
```

## arXiv submission notes

1. Each paper directory is a **standalone** submission unit (plus `../common/` macros and bibliography).
2. For upload, either:
   - flatten `common/` into each paper tree and rewrite `\input`/`\bibliography` paths, or
   - submit a zip with `common/` and paper sources preserving relative paths.
3. Prefer embedding TikZ (no external image binaries required for most figures).
4. Declare categories e.g. **primary** `cs.PL` with cross-lists as in the table above.
5. Include the trademark disclaimer (already in each abstract/intro).
6. Do **not** claim TradingView platform certification; papers document an independent reimplementation and internal dual-host parity.

Suggested arXiv comment line:

```text
Part of the PYNE open toolchain paper series. Companion papers describe compiler, series runtime, grammar, numerical parity, and LSP tooling.
```

## Content grounding

Technical claims are grounded in repository design and performance notes (2025–2026), including:

- `DESIGN.md`, `docs/COMPILER_PLAN.md`
- Performance rounds (`docs/perf_round*`, `docs/perf_agents_summary.md`)
- `docs/numerical_validation_report.md`, `docs/compatibility_guarantee.md`
- Implementation under `src/pynescript/` (grammar, AST, evaluator, compiler, langserver)

Benchmark numbers are **internal measurements** on representative scripts and hardware; they are not third-party audited platform benchmarks.

## License

Paper sources are part of the PYNE repository. Software is AGPL-3.0-or-later; check `LICENSE` at the repo root. When submitting to arXiv, authors may dual-license the text under a standard academic license (e.g. CC BY 4.0) if desired—update this README accordingly before submission.

## Companion product links

- Website: [hoox.sh/pyne](https://hoox.sh/pyne)
- Source: [github.com/hoox-sh/pyne](https://github.com/hoox-sh/pyne)
- PyPI: [`hoox-pyne`](https://pypi.org/project/hoox-pyne/)
