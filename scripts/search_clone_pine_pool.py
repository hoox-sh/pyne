#!/usr/bin/env python3
# Copyright (C) 2024-2026 jango_blockchained
#
# This file is part of pynescript.
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Search GitHub for Pine Script collections and shallow-clone them into a pool.

Companion to ``scripts/collect_pine_corpus.py``. Typical flow::

    python scripts/search_clone_pine_pool.py --pool .cache/pine-collect
    python scripts/collect_pine_corpus.py \\
        --pool .cache/pine-collect --set set06 --target 15000 \\
        --max-per-repo 100000 \\
        --libraries 2000 --strategies 8000 --indicators 8000 \\
        --prefer-version \\
        --exclude-manifest tests/data/set01/MANIFEST.json \\
        --exclude-manifest tests/data/set02/MANIFEST.json \\
        --exclude-manifest tests/data/set03/MANIFEST.json \\
        --exclude-manifest tests/data/set04/MANIFEST.json \\
        --exclude-manifest tests/data/set05/MANIFEST.json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import as_completed
from pathlib import Path

# High-yield sources from set01–set05 (always clone even if search misses them).
SEED_REPOS = [
    "everget/tradingview-pinescript-indicators",
    "Alorse/pinescript-strategies",
    "capissimo/Pinescript-Laboratory",
    "ricardosantos79/pinescript",
    "fmzquant/strategies",
    "hasnocool/tradingview-pine-scripts",
    "TradersPost/pinescript-agents",
    "mihakralj/pinescript",
    "mihakralj/QuanTAlib",
    "codenamedevan/pinescriptv6",
    "casoon/pine-scripts",
    "vikaschouhan/algotrade",
    "TraderOracle/TradingView",
    "f13end/tradingview-custom-indicators",
    "yeyingsrc/tradingview-indicators-pine",
    "benso87/Private-Pine-Scripts",
    "ArunKBhaskar/PineScript",
    "hirawatt/pineScripts",
    "getupandCROW/TradingView",
    "KivancOzbilgic/PineScript",
    "Heavy91/TradingView_Indicators",
    "aceri/tradingview_pinescript",
    "dgfctr/PineScript",
    "algocode2022/PineScript",
    "cryptorife/pine-scripts",
    "Zettt/pinescripts",
    "DillonGrech/Tradingview-Strategies",
    "SammyEnigma/pine-scripts",
    "thanhnguyennguyen/tradingview-pine-scripts",
    "oguzhandilber/PineScripts",
    "pradip-interra/PineScripts",
    "Salikha003/PineScripts",
    "TradeFab/Tradingview.public",
    "JackZhao516/Smrti-tradingview-pine-scripts",
    "Jaqobs/pinescripts",
    "dexcextrade/TradingView-PineScripts",
    "shaikhsharik/PineScripts",
    "sibvic/pinescript-templates",
    "tradesdontlie/pinescript-development-workspace",
    "tangly1024/TrendWaveTracker",
    "atomantic/pine_scripts",
    "razorbladekisses/Tradingview-Indicators",
    "ScavengerBot/TradingviewScripts",
    "azerhouani/TradingView_PineScripts",
    "chris-c-thomas/chrd-tradingview-pine-scripts",
    "LouisLetcher/quant-pine",
    "iamrichardD/mcp-server-pinescript",
    "pinecoders/pine-utils",
    "tradingstrategy-ai/tradingview-defi-strategy",
    "ZizkaJakub/Pinescripts",
    "shyrwinsia/pine-scripts",
    "sawantuday/pinescripts",
    "yankeexlr/tradingview",
]

SKIP_REPOS = {
    "hoox-sh/pyne",
    "hoox-sh/pyne-worker",
    "elbakramer/pynescript",
    "yaphott/pynescript",
    "PyneSys/pynecore",
    "pAulseperformance/awesome-pinescript",
    "just-nilux/awesome-tradingview",
    "LabinatorSolutions/awesome-institutional-trading",
    "pinecoders/pinecoders.github.io",
    "LuxAlgo/PineTS",
    "LuxAlgo/pinets-cli",
    "be-thomas/OpenPineScript",
    "pineforge-4pass/pineforge-engine",
    "heyphat/piner",
    "Opus-Aether-AI/pine-transpiler",
    "ferranbt/pinecone",
}

SKIP_NAME_RE = re.compile(
    r"(vscode|syntax[-_ ]highlight|udl|npp|cheatsheet|awesome[-_]"
    r"|pinephone|pine64|pinecone|mcp[-_]?server|transpil|compiler"
    r"|pynecore|opentrade|tvcontrol|pdfs?$|user[_-]manual)",
    re.I,
)

SEARCH_QUERIES = [
    "topic:pinescript",
    "topic:pine-script",
    "topic:pinescript-indicators",
    "topic:pinescript-strategies",
    "topic:tradingview-pine-scripts",
    "pinescript in:name",
    "pine-script in:name",
]


def _run(cmd: list[str], *, cwd: Path | None = None, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def search_repos(limit: int) -> list[str]:
    found: dict[str, None] = {}
    for seed in SEED_REPOS:
        found[seed] = None
    for query in SEARCH_QUERIES:
        proc = _run(
            [
                "gh",
                "search",
                "repos",
                query,
                "--limit",
                str(limit),
                "--json",
                "fullName",
            ],
            timeout=90,
        )
        if proc.returncode != 0:
            print(f"warn: search failed for {query!r}: {proc.stderr.strip()[:200]}", file=sys.stderr)
            continue
        try:
            rows = json.loads(proc.stdout)
        except json.JSONDecodeError:
            continue
        for row in rows:
            name = str(row.get("fullName") or "").strip()
            if name:
                found[name] = None
    return list(found)


def should_clone(full_name: str) -> bool:
    if full_name in SKIP_REPOS:
        return False
    owner, _, repo = full_name.partition("/")
    if SKIP_NAME_RE.search(full_name) or SKIP_NAME_RE.search(repo):
        return False
    if owner.lower() in {"hoox-sh"}:
        return False
    return True


def pool_dirname(full_name: str) -> str:
    owner, _, repo = full_name.partition("/")
    return f"{owner}-{repo}".replace("/", "-")


def clone_one(full_name: str, pool: Path) -> tuple[str, str]:
    dest = pool / pool_dirname(full_name)
    url = f"https://github.com/{full_name}.git"
    if dest.exists() and (dest / ".git").exists():
        return full_name, "exists"
    dest.parent.mkdir(parents=True, exist_ok=True)
    proc = _run(
        ["git", "clone", "--depth", "1", "--single-branch", url, str(dest)],
        timeout=180,
    )
    if proc.returncode == 0:
        return full_name, "cloned"
    err = (proc.stderr or proc.stdout or "").strip().splitlines()
    tail = err[-1] if err else f"exit {proc.returncode}"
    if dest.exists():
        # incomplete clone
        try:
            import shutil

            shutil.rmtree(dest)
        except OSError:
            pass
    return full_name, f"fail: {tail[:160]}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pool", type=Path, default=Path(".cache/pine-collect"))
    ap.add_argument("--search-limit", type=int, default=100, help="Per-query GitHub search limit (max 100).")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--skip-search", action="store_true", help="Only clone SEED_REPOS.")
    args = ap.parse_args()

    pool = args.pool.resolve()
    pool.mkdir(parents=True, exist_ok=True)

    names = list(SEED_REPOS)
    if not args.skip_search:
        print("searching GitHub…", flush=True)
        names = search_repos(args.search_limit)
    names = sorted({n for n in names if should_clone(n)}, key=str.lower)
    print(f"cloning {len(names)} repos → {pool}", flush=True)

    stats = {"cloned": 0, "exists": 0, "fail": 0}
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        futs = [ex.submit(clone_one, name, pool) for name in names]
        for i, fut in enumerate(as_completed(futs), 1):
            full_name, status = fut.result()
            key = status.split(":", 1)[0]
            stats[key] = stats.get(key, 0) + 1
            mark = "✔" if status in {"cloned", "exists"} else "✘"
            print(f"[{i}/{len(names)}] {mark} {full_name}  {status}", flush=True)

    print(json.dumps({"pool": str(pool), "wanted": len(names), **stats}, indent=2))
    return 0 if stats.get("fail", 0) == 0 or stats.get("cloned", 0) + stats.get("exists", 0) > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
