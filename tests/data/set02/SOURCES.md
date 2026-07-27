# Pine Script corpus sources — set02

Collected: 2026-07-27
Scripts in this set: **250**

Second batch after set01. Content hashes are **disjoint** from set01
(via `--exclude-manifest tests/data/set01/MANIFEST.json`).

## Composition targets vs actual

| Kind | Target | Actual |
| --- | ---: | ---: |
| Libraries | 40 | 40 |
| Strategies | 70 | 70 |
| Indicators | 140 | 140 |

## Pine version mix

| Version | Count |
| --- | ---: |
| v5 | 33 |
| v6 | 217 |

## Used in set02

| Repo dir (pool) | URL | Scripts | Notes |
| --- | --- | ---: | --- |
| pinescript-agents | [pinescript-agents](https://github.com/TradersPost/pinescript-agents) | 40 | TradersPost agents/templates (v6 strategies) |
| QuanTAlib | [QuanTAlib](https://github.com/mihakralj/QuanTAlib) | 40 | Quantitative indicators (cycles, transforms) |
| mihakralj-pinescript | [mihakralj-pinescript](https://github.com/mihakralj/pinescript) | 40 | Large public indicator library (MIT) |
| casoon-pine-scripts | [casoon-pine-scripts](https://github.com/casoon/pine-scripts) | 34 | Community indicators/strategies |
| fmzquant-strategies | [fmzquant-strategies](https://github.com/fmzquant/strategies) | 34 | Multi-language strategies; Pine subset |
| ricardosantos79-pinescript | [ricardosantos79-pinescript](https://github.com/ricardosantos79/pinescript) | 31 | Ricardo Santos libs + experiments |
| mcp-server-pinescript | [mcp-server-pinescript](https://github.com/iamrichardD/mcp-server-pinescript) | 8 | MCP-related pine samples |
| jbondata-pinescript-indicator-suite | [jbondata-pinescript-indicator-suite](https://github.com/jbondata/pinescript-indicator-suite) | 6 | ICT-style v6 suite |
| dgfctr-PineScript | [dgfctr-PineScript](https://github.com/dgfctr/PineScript) | 4 | Library pack (bands, trend systems) |
| TraderOracle-TradingView | [TraderOracle-TradingView](https://github.com/TraderOracle/TradingView) | 4 | TradingView scripts dump |
| LouisLetcher-quant-pine | [LouisLetcher-quant-pine](https://github.com/LouisLetcher/quant-pine) | 3 | Quant strategies/indicators |
| tradingview-ml-signals | [tradingview-ml-signals](https://github.com/GeekRabbit007/tradingview-ml-signals) | 2 | ML signal scripts |
| Zettt-pinescripts | [Zettt-pinescripts](https://github.com/Zettt/pinescripts) | 2 | Small personal collection |
| hirawatt-pineScripts | [hirawatt-pineScripts](https://github.com/hirawatt/pineScripts) | 1 | Indicators/strategies/libraries |
| devgaganin-pine-scripts | [devgaganin-pine-scripts](https://github.com/devgaganin/pine-scripts) | 1 | Small personal collection |

## How set02 was built

```bash
python scripts/collect_pine_corpus.py \
  --pool /tmp/pine-new-collect \
  --set set02 \
  --target 250 \
  --max-per-repo 40 \
  --libraries 40 --strategies 70 --indicators 140 \
  --prefer-version \
  --exclude-manifest tests/data/set01/MANIFEST.json
```

Pool at build time: **~9.5k unique** Pine candidates under
`/tmp/pine-new-collect` (after exclude of set01 hashes).

## Expansion notes (set03+)

- Remaining unique in pool after set01+set02: **thousands** (pool ~9.5k content hashes, used 500).
- High-yield dirs still underused under `/tmp/pine-new-collect`:
  - `hasnocool-tradingview-pine-scripts` (~1800 `.pine`, needs scrape-header cleanup)
  - `mihakralj-pinescript` (cap 40 / ~410, clean MIT v6)
  - `QuanTAlib` (cap 40 / ~400, complementary to mihakralj)
  - `fmzquant-strategies` (~5k `//@version` in `.md` fences — needs extract step)
  - `casoon-pine-scripts`, `tradingview-custom-indicators`, `TraderOracle-TradingView`
- Other scouted clean repos (may not all be in pool yet):
  - https://github.com/g-moe/Trading-Indicators
  - https://github.com/dcaoyuan/vibetrader
  - https://github.com/iamc1oud/Tradingview-Scripts
  - https://github.com/SiegerTerpstra/tradingview-basic
  - https://github.com/vikaschouhan/algotrade (`.psc` = Pine)
  - https://github.com/benso87/Private-Pine-Scripts
- Keep using `--exclude-manifest` for **both** set01 and set02 manifests:
  ```bash
  python scripts/collect_pine_corpus.py \
    --pool /tmp/pine-new-collect \
    --set set03 --target 250 --prefer-version --max-per-repo 40 \
    --libraries 40 --strategies 70 --indicators 140 \
    --exclude-manifest tests/data/set01/MANIFEST.json \
    --exclude-manifest tests/data/set02/MANIFEST.json
  ```
- Prefer `--prefer-version` + moderate `--max-per-repo` for diversity.
- Do **not** copy `tests/data/builtin_scripts/` or dump `tests/data/library/` wholesale.
- Skip near-mirrors of set01: `f13end/tradingview-custom-indicators` (≈ everget),
  `BeSmMo/pinescript2` (≈ Alorse).

## Related

- [set01 SOURCES](../set01/SOURCES.md)
- Collector: `scripts/collect_pine_corpus.py`

## Larger sets

- **set03** / **set04** — 1000 scripts each under `tests/data/set0{3,4}/`
- Combined corpus (set01–set04): **2500** unique scripts by content hash

