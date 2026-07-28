# PYNE brand graphics

Visual language matches [hoox.sh/pyne](https://hoox.sh/pyne): flat fields, micro-grid, mono noise, corner brackets, IBM Plex Mono. Monogram **P** (no HOOX mark).

## Headlines (from landing)

| Slug | Copy (always UPPERCASE in assets) |
| ---- | --------------------------------- |
| `parse-the-language` | PARSE THE LANGUAGE. OWN THE AST. |
| `grammar-to-semantics` | GRAMMAR TO SEMANTICS. |
| `own-the-bar-loop` | OWN THE BAR LOOP. |

Sources: hero H1 `[PARSE THE LANGUAGE. OWN THE AST.]`, eyebrow `GRAMMAR → SEMANTICS`, deploy/footer emphasis on owning the bar loop.

## Scripts

```bash
# Centered monogram kit (SVG)
python3 brand/generate-centered.py
python3 brand/generate-centered.py --raster   # + PNG

# Tagline banners
python3 brand/generate-taglines.py --clean
python3 brand/generate-taglines.py --raster
```

Requires `rsvg-convert` for PNG output (`librsvg2-bin` on Debian/Ubuntu).

## Colors

`dark` `#050505` · `orange` `#F97316` · `white` `#FAFAFA`
