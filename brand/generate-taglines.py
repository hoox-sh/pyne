#!/usr/bin/env python3
# Copyright (c) 2026 HOOX · PYNE · jango-blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
PYNE brand taglines — curated social/hero banners.

Headlines from https://hoox.sh/pyne (hero + footer):
  1. PARSE THE LANGUAGE. OWN THE AST.
  2. GRAMMAR TO SEMANTICS.
  3. OWN THE BAR LOOP.

Usage:
  python3 brand/generate-taglines.py
  python3 brand/generate-taglines.py --raster
  python3 brand/generate-taglines.py --clean
"""
from __future__ import annotations

import argparse
import html
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SVG_DIR = ROOT / "svg"
PNG_DIR = ROOT / "png"
FONT_FILE = ROOT / "fonts" / "ibm-plex-mono-v20-latin-500.ttf"
FONT = '"IBM Plex Mono", "JetBrains Mono", ui-monospace, monospace'
PRODUCT = "PYNE"
MONOGRAM = "P"

# Landing-page headlines (hero H1, eyebrow, deploy/footer emphasis)
TAGLINES = [
    ("parse-the-language", "Parse the language. Own the AST."),
    ("grammar-to-semantics", "Grammar to semantics."),
    ("own-the-bar-loop", "Own the bar loop."),
]

SIZES = [
    ("og-1200x630", 1200, 630),
    ("twitter-1500x500", 1500, 500),
    ("linkedin-1584x396", 1584, 396),
    ("github-1280x640", 1280, 640),
    ("blog-1600x900", 1600, 900),
    ("youtube-2560x1440", 2560, 1440),
]

CURATED = [
    ("cluster", ("dark", "white", "orange")),
    ("split", ("dark", "white")),
]

KEEP_RE = re.compile(
    r"^tagline-(parse-the-language|grammar-to-semantics|own-the-bar-loop)-"
    r"(og-1200x630|twitter-1500x500|linkedin-1584x396|github-1280x640|blog-1600x900|youtube-2560x1440)-"
    r"(br-bottom|br-split)-(dark|white|orange)\.(svg|png|jpg)$"
)


def theme(variant: str) -> dict:
    if variant == "orange":
        return dict(
            bg="#F97316",
            grid="#000000",
            grid_op=0.09,
            text="rgba(255,255,255,0.95)",
            bracket="#FFFFFF",
            noise_rgb=0,
            noise_a=0.08,
            fill="#FFFFFF",
            stroke="#FFFFFF",
        )
    if variant == "white":
        return dict(
            bg="#FAFAFA",
            grid="#0A0A0A",
            grid_op=0.08,
            text="rgba(10,10,10,0.90)",
            bracket="#0A0A0A",
            noise_rgb=0,
            noise_a=0.05,
            fill="#0A0A0A",
            stroke="#0A0A0A",
        )
    return dict(
        bg="#050505",
        grid="#FFFFFF",
        grid_op=0.07,
        text="rgba(245,245,245,0.92)",
        bracket="#FFFFFF",
        noise_rgb=1,
        noise_a=0.06,
        fill="#F5F5F5",
        stroke="#FFFFFF",
    )


def font_face() -> str:
    if not FONT_FILE.exists():
        return ""
    # Absolute file URL for rsvg-convert
    href = FONT_FILE.resolve().as_uri()
    return f"""  <style type="text/css">
    @font-face {{
      font-family: "IBM Plex Mono";
      src: url("{href}") format("truetype");
      font-weight: 500;
      font-style: normal;
    }}
  </style>"""


def monogram(cx: float, cy: float, size: float, fill: str, stroke: str) -> str:
    """Geometric monogram mark (letter) — no HOOX geometry."""
    fs = size * 0.72
    # Soft glow ring + letter
    r = size * 0.48
    return f"""  <g transform="translate({cx},{cy})">
    <circle r="{r}" fill="none" stroke="{stroke}" stroke-opacity="0.22" stroke-width="1.5"/>
    <circle r="{r * 0.78}" fill="none" stroke="{stroke}" stroke-opacity="0.12" stroke-width="1"/>
    <text x="0" y="0" fill="{fill}" font-family='{FONT}' font-size="{fs}" font-weight="500"
          letter-spacing="0.04em" text-anchor="middle" dominant-baseline="central">{MONOGRAM}</text>
  </g>"""


def defs(t: dict) -> str:
    return f"""  <defs>
    <pattern id="micro" width="5" height="5" patternUnits="userSpaceOnUse">
      <path d="M 5 0 L 0 0 0 5" fill="none" stroke="{t["grid"]}" stroke-opacity="{t["grid_op"]}" stroke-width="0.52"/>
    </pattern>
    <pattern id="major" width="30" height="30" patternUnits="userSpaceOnUse">
      <path d="M 30 0 L 0 0 0 30" fill="none" stroke="{t["grid"]}" stroke-opacity="{min(t["grid_op"] * 1.35, 0.18):.3f}" stroke-width="0.6"/>
    </pattern>
    <filter id="monoNoise" x="0" y="0" width="100%" height="100%" filterUnits="objectBoundingBox" color-interpolation-filters="sRGB">
      <feTurbulence type="fractalNoise" baseFrequency="1.25" numOctaves="2" seed="17" stitchTiles="stitch" result="n"/>
      <feColorMatrix in="n" type="matrix"
        values="0 0 0 0 {t["noise_rgb"]}
                0 0 0 0 {t["noise_rgb"]}
                0 0 0 0 {t["noise_rgb"]}
                0 0 0 {t["noise_a"]} 0"/>
    </filter>
  </defs>"""


def brackets(w: int, h: int, color: str, op: float = 0.22) -> str:
    t = max(12, int(min(w, h) * 0.022))
    arm = max(14, int(min(w, h) * 0.032))
    return f"""  <g stroke="{color}" stroke-width="1" opacity="{op}" fill="none" stroke-linecap="square">
    <path d="M {t} {t+arm} V {t} H {t+arm}"/>
    <path d="M {w-t} {h-t-arm} V {h-t} H {w-t-arm}"/>
  </g>"""


def split_tagline(text: str, max_chars: int = 40) -> list[str]:
    u = text.upper()
    if "PARSE THE LANGUAGE" in u and "OWN THE AST" in u:
        return ["PARSE THE LANGUAGE.", "OWN THE AST."]
    if "GRAMMAR TO SEMANTICS" in u:
        return ["GRAMMAR TO SEMANTICS."]
    if "OWN THE BAR LOOP" in u:
        return ["OWN THE BAR LOOP."]
    if ". " in text:
        a, b = text.split(". ", 1)
        return [a + ".", b]
    if len(text) <= max_chars:
        return [text]
    words, line1, line2, n = text.split(), [], [], 0
    for w in words:
        if n + len(w) + 1 <= max_chars and not line2:
            line1.append(w)
            n += len(w) + 1
        else:
            line2.append(w)
    return [" ".join(line1), " ".join(line2)] if line2 else [" ".join(line1)]


def text_el(lines, x, y, *, size, fill, anchor, tracking, line_gap=1.35) -> str:
    parts = []
    for i, line in enumerate(lines):
        dy = "0" if i == 0 else f"{line_gap}em"
        parts.append(f'<tspan x="{x}" dy="{dy}">{html.escape(line)}</tspan>')
    return f"""  <text x="{x}" y="{y}" fill="{fill}" font-family='{FONT}' font-size="{size}" font-weight="500"
        letter-spacing="{tracking * size:.2f}" text-anchor="{anchor}" dominant-baseline="hanging">{"".join(parts)}</text>"""


def banner(w: int, h: int, tagline: str, *, variant: str, mode: str) -> str:
    assert w != h, "1:1 disabled"
    t = theme(variant)
    display = tagline.upper()
    m = min(w, h)
    logo_px = m * 0.18
    fs = max(13, min(26, int(h * 0.068)))
    tracking = 0.12
    lines = split_tagline(display, max_chars=42 if w >= 1200 else 30)
    text_h = len(lines) * fs * 1.35
    pad_x, pad_y = w * 0.07, h * 0.16
    gap = max(40, int(m * 0.06))

    lx = w - pad_x - logo_px * 0.5
    ly = h - pad_y - logo_px * 0.5
    logo_bottom = ly + logo_px * 0.5

    if mode == "split":
        tx, ty, anchor = pad_x, pad_y, "start"
    else:
        tx = w - pad_x - logo_px - gap
        ty = logo_bottom - text_h
        ty = max(pad_y * 0.5, min(ty, h - pad_y - text_h))
        anchor = "end"

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" version="1.1">
{font_face()}
{defs(t)}
  <rect width="{w}" height="{h}" fill="{t["bg"]}"/>
  <rect width="{w}" height="{h}" fill="url(#micro)"/>
  <rect width="{w}" height="{h}" fill="url(#major)"/>
  <rect width="{w}" height="{h}" filter="url(#monoNoise)"/>
{brackets(w, h, t["bracket"], 0.2 if variant == "dark" else 0.28)}
{monogram(lx, ly, logo_px, t["fill"], t["stroke"])}
{text_el(lines, tx, ty, size=fs, fill=t["text"], anchor=anchor, tracking=tracking)}
</svg>
"""


def clean_non_curated() -> int:
    removed = 0
    for folder in (SVG_DIR, PNG_DIR):
        if not folder.exists():
            continue
        for f in list(folder.glob("tagline-*")):
            if not KEEP_RE.match(f.name):
                f.unlink()
                removed += 1
    return removed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raster", action="store_true")
    ap.add_argument("--clean", action="store_true")
    args = ap.parse_args()

    SVG_DIR.mkdir(parents=True, exist_ok=True)
    PNG_DIR.mkdir(parents=True, exist_ok=True)

    if args.clean:
        n = clean_non_curated()
        print(f"Removed {n} non-curated tagline files")

    names: list[str] = []
    for slug, text in TAGLINES:
        for size_name, w, h in SIZES:
            for mode, variants in CURATED:
                for variant in variants:
                    layout = "br-split" if mode == "split" else "br-bottom"
                    name = f"tagline-{slug}-{size_name}-{layout}-{variant}"
                    (SVG_DIR / f"{name}.svg").write_text(
                        banner(w, h, text, variant=variant, mode=mode)
                    )
                    names.append(name)

    print(f"[{PRODUCT}] Wrote {len(names)} curated tagline SVGs (always UPPERCASE)")
    print("  Taglines: PARSE THE LANGUAGE. OWN THE AST. | GRAMMAR TO SEMANTICS. | OWN THE BAR LOOP.")
    print("  Layouts: br-bottom (dark/white/orange), br-split (dark/white)")

    if args.raster:
        ok = 0
        for name in names:
            src, dst = SVG_DIR / f"{name}.svg", PNG_DIR / f"{name}.png"
            try:
                subprocess.run(
                    ["rsvg-convert", "-o", str(dst), str(src)],
                    check=True,
                    capture_output=True,
                )
                ok += 1
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                print(f"FAIL {name}: {e}", file=sys.stderr)
        print(f"[{PRODUCT}] Rasterized {ok}/{len(names)} → {PNG_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
