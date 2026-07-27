# Pine Script corpus sources — set01

Collected: 2026-07-27
Scripts in this set: **250**

This file lists public repositories used (or scouted) so the corpus can be
researched again and expanded (set02+, more scripts).

## Used in set01

| Repo | Author | Scripts used | Notes |
| --- | --- | ---: | --- |
| [tradingview-pinescript-indicators](https://github.com/everget/tradingview-pinescript-indicators) | everget | 90 | Large GPL-3.0 indicator collection (v4–v6) |
| [pinescript-strategies](https://github.com/Alorse/pinescript-strategies) | Alorse | 74 | Strategies + indicators with alerts |
| [Pinescript-Laboratory](https://github.com/capissimo/Pinescript-Laboratory) | capissimo | 44 | Laboratory collection |
| [pinescript](https://github.com/ricardosantos79/pinescript) | ricardosantos79 | 25 | Ricardo Santos Pine scripts |
| [TradingView](https://github.com/getupandCROW/TradingView) | getupandCROW | 13 | Indicators and strategies |
| [pineScripts](https://github.com/hirawatt/pineScripts) | hirawatt | 4 | Indicators, strategies, libraries |

## Scouted for expansion (not fully mined or low yield)

Re-check these when growing the corpus:

| Repo | URL | Why re-check |
| --- | --- | --- |
| pAulseperformance/awesome-pinescript | https://github.com/pAulseperformance/awesome-pinescript | Curated index of Pine resources (links, not always full sources) |
| just-nilux/awesome-tradingview | https://github.com/just-nilux/awesome-tradingview | Curated strategies/indicators/alerts index |
| fmzquant/strategies | https://github.com/fmzquant/strategies | Large multi-language strategy dump; filter Pine only |
| LuxAlgo public examples | https://www.tradingview.com/u/LuxAlgo/#published-scripts | Community scripts (respect licenses / open-source only) |
| TradingView Community Scripts | https://www.tradingview.com/scripts/ | Filter open-source; scrape carefully / ToS |
| TradingView Built-ins | (internal `tests/data/builtin_scripts/`) | Already in-repo; do not re-download |
| Local library | `tests/data/library/` | Existing private/community stash; not duplicated into set01 |

## Additional GitHub topics to search

- https://github.com/topics/pinescript
- https://github.com/topics/pinescript-indicators
- https://github.com/topics/pinescript-strategies
- https://github.com/topics/pine-script
- https://github.com/topics/tradingview-pine-scripts
- Query: `extension:pine indicator OR strategy OR library`
- Query: `//@version=5 language:Pine` (when language detection works)
- Query: `filename:*.pine path:/`

## Naming convention

```
tests/data/set01/
  indicators/NNN_ind_<slug>.pine
  strategies/NNN_str_<slug>.pine
  libraries/NNN_lib_<slug>.pine
  MANIFEST.json
  SOURCES.md
  README.md
```

- `NNN` = zero-padded global id within the set
- `ind` / `str` / `lib` = kind
- `slug` = sanitized title from `indicator()`/`strategy()`/`library()` declaration
- Each file starts with `//@version=…` (when present) then provenance comments

## Re-run / expand

Pool snapshot when set01 was built: **~890 unique** Pine scripts across the
repos under `/tmp/pine-collect` (set01 kept 250 with diversity quotas).

```bash
# 1) Refresh / extend the clone pool
mkdir -p /tmp/pine-collect && cd /tmp/pine-collect
git clone --depth 1 https://github.com/everget/tradingview-pinescript-indicators.git
# ... add more repos from tables above ...

# 2) Build the next set (example: 250 more into set02)
cd /path/to/pynescript
python scripts/collect_pine_corpus.py \
  --pool /tmp/pine-collect \
  --set set02 \
  --target 250 \
  --libraries 30 --strategies 80 --indicators 140
```

Pipeline steps (also implemented by `scripts/collect_pine_corpus.py`):

1. Clone additional sources into a temp dir
2. Detect Pine via `//@version=` or `indicator|strategy|library|study(`
3. Deduplicate by content SHA-256
4. Classify by declaration, then path heuristics
5. Emit next set as `tests/data/set02/` with a fresh id space
6. Update this SOURCES list with new repos

## License note

Scripts retain their original licenses (often MIT/GPL/MPL or author-stated).
Provenance headers point back to the GitHub source path. Do not republish
as your own work; this corpus is for parser/evaluator/test coverage.

## Related sets

- **set02** (`tests/data/set02/`) — 250 more scripts, hash-disjoint from set01,
  skewed to Pine **v5/v6** (see set02 `SOURCES.md`). Built with
  `--exclude-manifest tests/data/set01/MANIFEST.json --prefer-version`.
- Combined corpus size: **500** scripts under `tests/data/set0{1,2}/`.

## Larger sets

- **set03** / **set04** — 1000 scripts each under `tests/data/set0{3,4}/`
- Combined corpus (set01–set04): **2500** unique scripts by content hash

