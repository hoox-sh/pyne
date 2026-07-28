#!/usr/bin/env python3
# Copyright (c) 2026 HOOX · PYNE · jango-blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Generate pure centered-logo brand assets for PYNE.

- Product monogram mark (not HOOX geometry)
- Centered mark, flat bg, micro-grid, mono noise
- Colors: dark | orange | white

Usage:
  python3 brand/generate-centered.py
  python3 brand/generate-centered.py --raster
"""
from __future__ import annotations

import argparse
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

SPECS = [
    ("og-1200x630", 1200, 630, "centered"),
    ("twitter-header-1500x500", 1500, 500, "centered"),
    ("linkedin-banner-1584x396", 1584, 396, "centered"),
    ("github-social-1280x640", 1280, 640, "centered"),
    ("blog-hero-1600x900", 1600, 900, "centered"),
    ("youtube-channel-2560x1440", 2560, 1440, "centered"),
    ("discord-banner-960x540", 960, 540, "centered"),
    ("email-header-600x200", 600, 200, "centered"),
    ("profile-1024", 1024, 1024, "icon"),
    ("profile-512", 512, 512, "icon"),
    ("app-icon-512", 512, 512, "icon"),
    ("app-icon-192", 192, 192, "icon"),
    ("slack-500", 500, 500, "icon"),
    ("wallpaper-1920x1080", 1920, 1080, "watermark"),
    ("wallpaper-2560x1440", 2560, 1440, "watermark"),
]
VARIANTS = ("dark", "orange", "white")


def theme(variant: str) -> dict:
    if variant == "orange":
        return dict(
            bg="#F97316", grid="#000000", grid_op=0.09,
            fill="#FFFFFF", stroke="#FFFFFF", bracket="#FFFFFF",
            noise_rgb=0, noise_a=0.08, bracket_op=0.35,
        )
    if variant == "white":
        return dict(
            bg="#FAFAFA", grid="#0A0A0A", grid_op=0.08,
            fill="#0A0A0A", stroke="#0A0A0A", bracket="#0A0A0A",
            noise_rgb=0, noise_a=0.05, bracket_op=0.28,
        )
    return dict(
        bg="#050505", grid="#FFFFFF", grid_op=0.07,
        fill="#F5F5F5", stroke="#FFFFFF", bracket="#FFFFFF",
        noise_rgb=1, noise_a=0.07, bracket_op=0.28,
    )


def font_face() -> str:
    if not FONT_FILE.exists():
        return ""
    href = FONT_FILE.resolve().as_uri()
    return (
        '  <style type="text/css">\n'
        '    @font-face {\n'
        '      font-family: "IBM Plex Mono";\n'
        f'      src: url("{href}") format("truetype");\n'
        '      font-weight: 500;\n'
        '      font-style: normal;\n'
        '    }\n'
        '  </style>'
    )


def monogram(cx: float, cy: float, size: float, fill: str, stroke: str) -> str:
    r = size * 0.48
    fs = size * 0.72
    axes = ""

    return f"""  <g transform="translate({cx},{cy})">
    <circle r="{r}" fill="none" stroke="{stroke}" stroke-opacity="0.22" stroke-width="1.5"/>
    <circle r="{r * 0.78}" fill="none" stroke="{stroke}" stroke-opacity="0.12" stroke-width="1"/>
{axes}
    <text x="0" y="0" fill="{fill}" font-family='{FONT}' font-size="{fs}" font-weight="500"
          letter-spacing="0.04em" text-anchor="middle" dominant-baseline="central">{MONOGRAM}</text>
  </g>"""


def brackets(w: int, h: int, color: str, op: float) -> str:
    t = max(12, int(min(w, h) * 0.022))
    arm = max(14, int(min(w, h) * 0.032))
    return f"""  <g stroke="{color}" stroke-width="1.25" opacity="{op}" fill="none" stroke-linecap="square">
    <path d="M {t} {t+arm} V {t} H {t+arm}"/>
    <path d="M {w-t} {h-t-arm} V {h-t} H {w-t-arm}"/>
  </g>"""


def make_svg(w: int, h: int, *, variant: str, style: str) -> str:
    t = theme(variant)
    m = min(w, h)
    if style == "icon":
        logo_frac = 0.70
    elif style == "watermark":
        logo_frac = 0.32
    else:
        logo_frac = 0.48 if h / max(w, 1) < 0.45 else 0.42
    logo_px = m * logo_frac
    cx, cy = w * 0.5, h * 0.5
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" version="1.1">
{font_face()}
  <defs>
    <pattern id="micro" width="5" height="5" patternUnits="userSpaceOnUse">
      <path d="M 5 0 L 0 0 0 5" fill="none" stroke="{t["grid"]}" stroke-opacity="{t["grid_op"]}" stroke-width="0.52"/>
    </pattern>
    <pattern id="major" width="30" height="30" patternUnits="userSpaceOnUse">
      <path d="M 30 0 L 0 0 0 30" fill="none" stroke="{t["grid"]}" stroke-opacity="{min(t["grid_op"] * 1.35, 0.18):.3f}" stroke-width="0.6"/>
    </pattern>
    <filter id="monoNoise" x="0" y="0" width="100%" height="100%" filterUnits="objectBoundingBox" color-interpolation-filters="sRGB">
      <feTurbulence type="fractalNoise" baseFrequency="1.2" numOctaves="2" seed="11" stitchTiles="stitch" result="n"/>
      <feColorMatrix in="n" type="matrix"
        values="0 0 0 0 {t["noise_rgb"]}
                0 0 0 0 {t["noise_rgb"]}
                0 0 0 0 {t["noise_rgb"]}
                0 0 0 {t["noise_a"]} 0"/>
    </filter>
  </defs>
  <rect width="{w}" height="{h}" fill="{t["bg"]}"/>
  <rect width="{w}" height="{h}" fill="url(#micro)"/>
  <rect width="{w}" height="{h}" fill="url(#major)"/>
  <rect width="{w}" height="{h}" filter="url(#monoNoise)"/>
{brackets(w, h, t["bracket"], t["bracket_op"])}
{monogram(cx, cy, logo_px, t["fill"], t["stroke"])}
</svg>
"""


def write_transparent_marks() -> list[str]:
    out = []
    for fill, name in (
        ("#FFFFFF", "mark-white-transparent-1024"),
        ("#F97316", "mark-orange-transparent-1024"),
        ("#0A0A0A", "mark-black-transparent-1024"),
    ):
        svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 1024 1024" version="1.1">
{font_face()}
{monogram(512, 512, 1024 * 0.70, fill, fill)}
</svg>
"""
        (SVG_DIR / f"{name}.svg").write_text(svg)
        out.append(name)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raster", action="store_true")
    args = ap.parse_args()
    SVG_DIR.mkdir(parents=True, exist_ok=True)
    PNG_DIR.mkdir(parents=True, exist_ok=True)
    names: list[str] = []
    for base, w, h, style in SPECS:
        for variant in VARIANTS:
            name = f"{base}-{variant}"
            (SVG_DIR / f"{name}.svg").write_text(make_svg(w, h, variant=variant, style=style))
            names.append(name)
    names.extend(write_transparent_marks())
    print(f"[{PRODUCT}] Wrote {len(names)} centered-logo SVGs → {SVG_DIR}")
    if args.raster:
        ok = 0
        for name in names:
            src, dst = SVG_DIR / f"{name}.svg", PNG_DIR / f"{name}.png"
            try:
                subprocess.run(["rsvg-convert", "-o", str(dst), str(src)], check=True, capture_output=True)
                ok += 1
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                print(f"FAIL {name}: {e}", file=sys.stderr)
        print(f"[{PRODUCT}] Rasterized {ok}/{len(names)} PNGs → {PNG_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
