# Pine Script corpus sources — set03

Collected: 2026-07-27
Scripts in this set: **1000**

Large batch. Content hashes are **disjoint** from set01, set02
(via `--exclude-manifest` for each prior set).

## Composition

| Kind | Count |
| --- | ---: |
| Librarys | 32 |
| Strategys | 251 |
| Indicators | 717 |

## Pine version mix

| Version | Count |
| --- | ---: |
| v5 | 6 |
| v6 | 985 |
| vNone | 9 |

## Used repos

| Repo (pool dir) | URL | Scripts | Notes |
| --- | --- | ---: | --- |
| `fmzquant-strategies` | [fmzquant-strategies](https://github.com/fmzquant/strategies) | 200 | Pine fenced in strategy markdown (FMZ bulk dump) |
| `QuanTAlib` | [QuanTAlib](https://github.com/mihakralj/QuanTAlib) | 200 | Quantitative indicator library (Apache) |
| `mihakralj-pinescript` | [mihakralj-pinescript](https://github.com/mihakralj/pinescript) | 200 | Large MIT indicator suite (v6) |
| `pinescript-agents` | [pinescript-agents](https://github.com/TradersPost/pinescript-agents) | 194 | TradersPost agents + strategy templates (v6) |
| `casoon-pine-scripts` | [casoon-pine-scripts](https://github.com/casoon/pine-scripts) | 87 | Community indicators/strategies |
| `pinescriptv6` | [pinescriptv6](https://github.com/codenamedevan/pinescriptv6) | 78 | v6 reference / sample scripts |
| `chrd-tradingview-pine-scripts` | [chrd-tradingview-pine-scripts](https://github.com/chris-c-thomas/chrd-tradingview-pine-scripts) | 14 | MTF / equity tools (v6) |
| `dgfctr-PineScript` | [dgfctr-PineScript](https://github.com/dgfctr/PineScript) | 8 | Libraries (bands, trend systems) |
| `algocode2022-PineScript` | [algocode2022-PineScript](https://github.com/algocode2022/PineScript) | 5 | Personal pine collection |
| `TraderOracle-TradingView` | [TraderOracle-TradingView](https://github.com/TraderOracle/TradingView) | 3 | Personal TV script collection |
| `pinescript-development-workspace` | [pinescript-development-workspace](https://github.com/tradesdontlie/pinescript-development-workspace) | 3 | Dev workspace samples |
| `PinescriptV6-docs-crawler` | [PinescriptV6-docs-crawler](https://github.com/FaustoS88/PinescriptV6-docs-crawler) | 2 | Docs crawler examples |
| `dexcextrade-TradingView-PineScripts` | [dexcextrade-TradingView-PineScripts](https://github.com/dexcextrade/TradingView-PineScripts) | 1 | TV pinescript dump |
| `LouisLetcher-quant-pine` | [LouisLetcher-quant-pine](https://github.com/LouisLetcher/quant-pine) | 1 | Quant strategies |
| `strat-alerts` | [strat-alerts](https://github.com/yomerosho/strat-alerts) | 1 | Alert strategies |
| `nadi984-tradingview-indicator` | [nadi984-tradingview-indicator](https://github.com/nadi984/tradingview-indicator) | 1 | Single indicators |
| `jbondata-pinescript-indicator-suite` | [jbondata-pinescript-indicator-suite](https://github.com/jbondata/pinescript-indicator-suite) | 1 | ICT-style v6 suite |
| `mcp-server-pinescript` | [mcp-server-pinescript](https://github.com/iamrichardD/mcp-server-pinescript) | 1 | MCP pine samples |

## Build command

```bash
python scripts/collect_pine_corpus.py \
  --pool /tmp/pine-new-collect \
  --set set03 \
  --target 1000 \
  --max-per-repo 200 \
  --libraries 80 --strategies 250 --indicators 670 \
  --prefer-version \
  --exclude-manifest tests/data/set01/MANIFEST.json \
  --exclude-manifest tests/data/set02/MANIFEST.json
```

Pool unique candidates at build: **11131**
Skipped: `{'not_pine': 4892, 'unreadable_or_size': 221, 'excluded_manifest': 363, 'duplicate_hash': 942}`

## Layout

```
tests/data/set03/
  indicators/NNNN_ind_<slug>.pine
  strategies/NNNN_str_<slug>.pine
  libraries/NNNN_lib_<slug>.pine
  MANIFEST.json
  SOURCES.md
  README.md
```

## Related

- [set01](../set01/SOURCES.md) · [set02](../set02/SOURCES.md) · [set03](../set03/SOURCES.md) · [set04](../set04/SOURCES.md)
- Collector: `scripts/collect_pine_corpus.py` (supports MD fence extraction + scrape cleanup)

