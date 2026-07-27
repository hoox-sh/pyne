#!/usr/bin/env python3
"""Collect open-source Pine Script into tests/data/setNN/.

Usage examples:

  # Process an already-cloned pool of GitHub repos:
  python scripts/collect_pine_corpus.py \\
      --pool /tmp/pine-collect \\
      --set set01 \\
      --target 250

  # Next batch, exclude prior set hashes and prefer newer Pine:
  python scripts/collect_pine_corpus.py \\
      --pool /tmp/pine-collect \\
      --set set02 \\
      --target 250 \\
      --libraries 40 --strategies 70 --indicators 140 \\
      --max-per-repo 60 \\
      --prefer-version \\
      --exclude-manifest tests/data/set01/MANIFEST.json

Re-clone popular sources (shallow) into a pool directory first, e.g.:

  mkdir -p /tmp/pine-collect && cd /tmp/pine-collect
  git clone --depth 1 https://github.com/everget/tradingview-pinescript-indicators.git
  # ... see tests/data/set01/SOURCES.md for the full list
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

MIN_BYTES = 80
MAX_BYTES = 1_500_000

SKIP_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".webp",
    ".pdf",
    ".zip",
    ".json",
    ".yml",
    ".yaml",
    ".toml",
    ".lock",
    ".css",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".html",
    ".pack",
    ".idx",
    ".rev",
    ".sample",
    ".csv",
    ".map",
    ".woff",
    ".woff2",
    ".ttf",
}

# Fenced code blocks that often hold Pine inside Markdown strategy dumps.
FENCED_PINE_RE = re.compile(
    r"```(?:pine(?:script)?|pinescript|tradingview)?\s*\n(.*?)```",
    re.S | re.I,
)
# Scraped TradingView dumps sometimes prefix every line with "  12|" line numbers.
LINE_NUM_PREFIX_RE = re.compile(r"^\s*\d+\|", re.M)

PINE_MARKERS = re.compile(
    r"(//@version\s*=|^\s*(indicator|strategy|library|study)\s*\()",
    re.M | re.I,
)
VERSION_RE = re.compile(r"//@version\s*=\s*(\d+)", re.I)
DECL_RE = re.compile(
    r"^\s*(indicator|strategy|library|study)\s*\(\s*(['\"])(.*?)\2",
    re.M | re.I,
)
TYPE_DECL_RE = re.compile(r"^\s*(indicator|strategy|library|study)\s*\(", re.M | re.I)

# Prefer these repos when present under --pool (lower = better).
# Biased toward underused/modern collections for later sets.
REPO_RANK = {
    "pinescript-indicator-suite": 0,
    "PineScript": 1,
    "pine-script-indicators": 2,
    "TradingView-Proprietary-Indicators": 3,
    "strategies": 4,
    "pinescript": 5,
    "Pinescript-Laboratory": 6,
    "pineScripts": 7,
    "TradingView": 8,
    "pinescript_practice": 9,
    "tradingview_scripts": 10,
    "pinescript-indicators": 11,
    "quant-pine": 12,
    "tradingview-pine-scripts": 13,
    "Tradingview-Indicators": 14,
    "TradingView_Indicators": 15,
    "trading-scripts": 16,
    "tradingview-pinescript": 17,
    "pinescript-strategies": 18,
    "tradingview-pinescript-indicators": 19,
    "TradingView-Scripts-1": 30,
    "tradingview-script-bundle": 31,
}


def slugify(name: str) -> str:
    name = re.sub(r"\.(pine|pinescript|txt|md)$", "", name.strip(), flags=re.I)
    name = re.sub(
        r"^\[(indicator|strategy|library|scanner|screener|readme|screenshot)\]\s*",
        "",
        name,
        flags=re.I,
    )
    name = re.sub(
        r"^(indicator|strategy|library|scanner|screener)\s*[-:]\s*",
        "",
        name,
        flags=re.I,
    )
    name = re.sub(r"\[[^\]]{1,40}\]", " ", name)
    name = name.lower().replace("&", " and ").replace("+", " plus ").replace("%", " pct ")
    name = re.sub(r"[^a-z0-9]+", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return (name or "unnamed")[:80]


def is_candidate(path: Path) -> bool:
    if ".git" in path.parts or path.is_dir():
        return False
    # never walk VCS / node / build noise
    if any(part in {".git", "node_modules", "dist", "__pycache__", ".next"} for part in path.parts):
        return False
    name_l = path.name.lower()
    if path.suffix.lower() in SKIP_SUFFIXES:
        return False
    if name_l.startswith("[preview]") or "screenshot" in name_l:
        return False
    if name_l in {"readme first.txt", "readme.md", "license", "license.md", "package.json"}:
        return False
    return True


def read_text(path: Path) -> str | None:
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if len(raw) < MIN_BYTES or len(raw) > MAX_BYTES or b"\x00" in raw[:1024]:
        return None
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return None


def clean_scraped_pine(text: str) -> str:
    """Normalize TradingView scrape wrappers (line numbers, NBSP, headers)."""
    text = text.replace("\u00a0", " ").replace("\ufeff", "")
    if LINE_NUM_PREFIX_RE.search(text[:2000]):
        text = LINE_NUM_PREFIX_RE.sub("", text)
    # Drop common scrape banners above //@version
    m = VERSION_RE.search(text)
    if m and m.start() > 0:
        head = text[: m.start()]
        if re.search(r"(script name|copy code|tradingview\.com/script)", head, re.I):
            text = text[m.start() :]
    return text


def extract_pine_bodies(path: Path, text: str) -> list[tuple[str, str]]:
    """Return list of (source_label, body) candidates from a file.

    Plain pine files yield one body. Markdown may yield multiple fenced blocks.
    """
    suffix = path.suffix.lower()
    bodies: list[tuple[str, str]] = []

    if suffix in {".md", ".markdown", ".rst"}:
        blocks = FENCED_PINE_RE.findall(text)
        if not blocks and ("//@version" in text or "indicator(" in text or "strategy(" in text):
            # Loose extract: from first //@version / declaration to end-ish
            m = re.search(
                r"(//@version\s*=.*|(?:^|\n)\s*(?:indicator|strategy|library|study)\s*\(.*)",
                text,
                re.S | re.I,
            )
            if m:
                blocks = [m.group(0)]
        for i, block in enumerate(blocks):
            body = clean_scraped_pine(block.strip())
            if body:
                label = f"{path.name}#block{i + 1}" if len(blocks) > 1 else path.name
                bodies.append((label, body))
        return bodies

    body = clean_scraped_pine(text)
    bodies.append((path.name, body))
    return bodies


def looks_like_pine(text: str) -> bool:
    if not PINE_MARKERS.search(text):
        return False
    score = 0
    for tok in (
        "plot(",
        "input.",
        "ta.",
        "math.",
        "request.",
        "strategy.",
        "hline(",
        "fill(",
        "array.",
        "var ",
        "bar_index",
        "security(",
        "sma(",
        "ema(",
        "rsi(",
        "atr(",
        "crossover(",
        "crossunder(",
        "study(",
        "indicator(",
        "strategy(",
        "library(",
    ):
        if tok in text:
            score += 1
    return score >= 1 or bool(VERSION_RE.search(text))


def classify(text: str, path: Path) -> str:
    m = TYPE_DECL_RE.search(text)
    if m:
        kind = m.group(1).lower()
        return "indicator" if kind == "study" else kind
    name = (path.name + " " + str(path)).lower().replace("\\", "/")
    if "library" in name or re.search(r"\blib\b", name):
        return "library"
    if "strategy" in name or "/strategies/" in name:
        return "strategy"
    return "indicator"


def extract_title(text: str, fallback: str) -> str:
    m = DECL_RE.search(text)
    return (m.group(3).strip() if m else "") or fallback


def extract_version(text: str) -> int | None:
    m = VERSION_RE.search(text)
    return int(m.group(1)) if m else None


def content_hash(text: str) -> str:
    norm = re.sub(r"\r\n?", "\n", text).strip()
    return hashlib.sha256(norm.encode("utf-8", errors="replace")).hexdigest()[:16]


def repo_of(path: Path, pool: Path) -> str:
    try:
        return path.relative_to(pool).parts[0]
    except Exception:
        return "unknown"


def load_exclude_hashes(manifest_paths: list[Path]) -> set[str]:
    """Load content_hash values from prior set MANIFEST.json files."""
    excluded: set[str] = set()
    for path in manifest_paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        for entry in data.get("scripts", []):
            h = entry.get("content_hash")
            if h:
                excluded.add(h)
    return excluded


def collect(
    pool: Path,
    out: Path,
    target: int,
    max_per_repo: int,
    kind_quota: dict[str, int],
    exclude_hashes: set[str] | None = None,
    prefer_version: bool = False,
) -> dict:
    exclude_hashes = exclude_hashes or set()
    candidates: list[dict] = []
    seen: set[str] = set()
    skipped: Counter[str] = Counter()

    for path in pool.rglob("*"):
        if not is_candidate(path):
            continue
        # Allow .md through for fenced-pine extraction (normally docs-only skip)
        text = read_text(path)
        if text is None:
            skipped["unreadable_or_size"] += 1
            continue
        for label, body in extract_pine_bodies(path, text):
            if not looks_like_pine(body):
                skipped["not_pine"] += 1
                continue
            h = content_hash(body)
            if h in exclude_hashes:
                skipped["excluded_manifest"] += 1
                continue
            if h in seen:
                skipped["duplicate_hash"] += 1
                continue
            seen.add(h)
            kind = classify(body, path)
            title = extract_title(body, Path(label).stem)
            slug = slugify(title if title else Path(label).stem)
            if slug in {"untitled", "unnamed", "my_script", "script"}:
                slug = slugify(path.stem)
            repo = repo_of(path, pool)
            source_rel = str(path.relative_to(pool))
            if label != path.name:
                source_rel = f"{source_rel}::{label}"
            candidates.append(
                {
                    "path": str(path),
                    "repo": repo,
                    "kind": kind,
                    "title": title,
                    "slug": slug,
                    "version": extract_version(body),
                    "hash": h,
                    "bytes": len(body.encode("utf-8")),
                    "lines": body.count("\n") + 1,
                    "text": body,
                    "source_rel": source_rel,
                }
            )

    def quality_key(c: dict) -> tuple:
        repo_rank = REPO_RANK.get(c["repo"], 25)
        ver = c["version"] or 0
        size_score = abs(c["lines"] - 120)
        is_pine_ext = 0 if c["path"].endswith((".pine", ".pinescript")) else 1
        # prefer_version: rank by Pine version first so v5/v6 fill before v3
        if prefer_version:
            return (-ver, repo_rank, is_pine_ext, size_score, c["slug"])
        return (repo_rank, -ver, is_pine_ext, size_score, c["slug"])

    candidates.sort(key=quality_key)

    selected: list[dict] = []
    per_repo: Counter[str] = Counter()
    slug_used: set[str] = set()

    def try_add(c: dict) -> bool:
        if any(s["hash"] == c["hash"] for s in selected):
            return False
        if per_repo[c["repo"]] >= max_per_repo:
            return False
        base = c["slug"]
        slug = base
        n = 2
        while f"{c['kind']}:{slug}" in slug_used:
            slug = f"{base}_{n}"
            n += 1
        entry = dict(c)
        entry["final_slug"] = slug
        slug_used.add(f"{c['kind']}:{slug}")
        selected.append(entry)
        per_repo[c["repo"]] += 1
        return True

    for want_kind, want_n in kind_quota.items():
        for c in candidates:
            if len([s for s in selected if s["kind"] == want_kind]) >= want_n:
                break
            if c["kind"] != want_kind:
                continue
            try_add(c)
            if len(selected) >= target:
                break
        if len(selected) >= target:
            break

    if len(selected) < target:
        for c in candidates:
            if len(selected) >= target:
                break
            try_add(c)

    if out.exists():
        shutil.rmtree(out)
    for sub in ("indicators", "strategies", "libraries"):
        (out / sub).mkdir(parents=True, exist_ok=True)

    today = datetime.now(timezone.utc).date().isoformat()
    # 4-digit ids once batches reach 1000+ so lexical sort stays ordered
    id_width = 4 if target >= 1000 or len(selected) >= 1000 else 3
    manifest_entries = []
    for i, c in enumerate(selected, 1):
        kind_dir = {"indicator": "indicators", "strategy": "strategies", "library": "libraries"}[c["kind"]]
        prefix = {"indicator": "ind", "strategy": "str", "library": "lib"}[c["kind"]]
        fname = f"{i:0{id_width}d}_{prefix}_{c['final_slug']}.pine"
        out_path = out / kind_dir / fname
        header = (
            f"// {out.name} corpus entry\n"
            f"// source_repo: {c['repo']}\n"
            f"// source_path: {c['source_rel']}\n"
            f"// content_hash: {c['hash']}\n"
            f"// collected: {today}\n"
        )
        body = c["text"]
        lines = body.splitlines(keepends=True)
        if lines and lines[0].lstrip().startswith("//@version"):
            new_body = lines[0] + header + "".join(lines[1:])
        else:
            new_body = header + body
        if not new_body.endswith("\n"):
            new_body += "\n"
        out_path.write_text(new_body, encoding="utf-8")
        manifest_entries.append(
            {
                "id": i,
                "file": f"{kind_dir}/{fname}",
                "kind": c["kind"],
                "title": c["title"],
                "slug": c["final_slug"],
                "pine_version": c["version"],
                "lines": c["lines"],
                "bytes": c["bytes"],
                "content_hash": c["hash"],
                "source_repo": c["repo"],
                "source_path": c["source_rel"],
            }
        )

    per_kind = Counter(e["kind"] for e in manifest_entries)
    manifest = {
        "set": out.name,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "target_count": target,
        "actual_count": len(manifest_entries),
        "pool_unique_candidates": len(candidates),
        "skipped": dict(skipped),
        "counts_by_kind": dict(per_kind),
        "counts_by_repo": dict(Counter(e["source_repo"] for e in manifest_entries)),
        "counts_by_pine_version": dict(Counter(str(e["pine_version"]) for e in manifest_entries)),
        "scripts": manifest_entries,
    }
    (out / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    readme = f"""# {out.name} — Pine Script corpus

| | |
| --- | ---: |
| Scripts | {len(manifest_entries)} |
| Indicators | {per_kind.get('indicator', 0)} |
| Strategies | {per_kind.get('strategy', 0)} |
| Libraries | {per_kind.get('library', 0)} |
| Pool unique candidates | {len(candidates)} |
| Collected | {today} |

See SOURCES.md (if present) and MANIFEST.json for provenance.
"""
    (out / "README.md").write_text(readme, encoding="utf-8")
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pool", type=Path, required=True, help="Directory containing cloned repos or .pine files")
    ap.add_argument("--set", dest="set_name", default="set01", help="Output set name under tests/data/")
    ap.add_argument("--out-root", type=Path, default=Path("tests/data"), help="Parent of set directory")
    ap.add_argument("--target", type=int, default=250, help="Number of scripts to keep")
    ap.add_argument("--max-per-repo", type=int, default=90)
    ap.add_argument("--libraries", type=int, default=25)
    ap.add_argument("--strategies", type=int, default=80)
    ap.add_argument("--indicators", type=int, default=145)
    ap.add_argument(
        "--exclude-manifest",
        action="append",
        default=[],
        type=Path,
        help="Prior set MANIFEST.json whose content_hash values to skip (repeatable)",
    )
    ap.add_argument(
        "--prefer-version",
        action="store_true",
        help="Rank candidates by Pine //@version first (favors v5/v6)",
    )
    args = ap.parse_args()

    out = args.out_root / args.set_name
    kind_quota = {
        "library": args.libraries,
        "strategy": args.strategies,
        "indicator": args.indicators,
    }
    exclude_hashes = load_exclude_hashes([p.resolve() for p in args.exclude_manifest])
    manifest = collect(
        args.pool.resolve(),
        out.resolve(),
        args.target,
        args.max_per_repo,
        kind_quota,
        exclude_hashes=exclude_hashes,
        prefer_version=args.prefer_version,
    )
    summary_keys = (
        "set",
        "actual_count",
        "counts_by_kind",
        "counts_by_repo",
        "counts_by_pine_version",
        "pool_unique_candidates",
        "skipped",
    )
    print(json.dumps({k: manifest[k] for k in summary_keys}, indent=2))
    print(f"Wrote {out} ({manifest['actual_count']} scripts)")


if __name__ == "__main__":
    main()
