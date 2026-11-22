# Handoff: align VERSION with `__about__.__version__`

from: oo-spec-2 (Deploy)
to: oo-checker / Chief
date: 2026-11-16
objective: Align package version sources. Authoritative is `src/pynescript/__about__.py` (`__version__ = "0.7.1"`). Root `VERSION` was stale at `0.7.0`.

## Artifacts
- `VERSION`: `0.7.0` → `0.7.1`
- `README.md`: live badge `**0.7.0**` → `**0.7.1**` (same drift)
- `docs/pinescript_implementation_status.md`, `docs/ROADMAP.md`, `docs/missing_features.md`: Live package pin `0.7.0` → `0.7.1`
- HQ card: `pynescript: VERSION file says 0.7.0 while __about__.__version__ is 0.7.1`

## Decisions
- Authoritative source remains `src/pynescript/__about__.py` (Hatch version path). `VERSION` is a mirror and was left behind after 0.7.1.
- Fixed only live pins that still claimed 0.7.0 for the current package. Left alone: CHANGELOG historical `## [0.7.0]` section, docker `TAG=0.7.0` bake examples / GHCR tags (release artifacts, not bumped here), flask-sock dependency pins, and generated export dumps under `docs/exports/` / `okf/docs/`.
- No commit, tag, push, or release.

## Proof
```text
before VERSION: 0.7.0
after  VERSION: 0.7.1
__about__.py: __version__ = "0.7.1"
match=True (python assert VERSION == about)
README live badge: **0.7.1**
docs Live package lines: 0.7.1
```

Minimal check:
```bash
python3 -c 'from pathlib import Path; import re; v=Path("VERSION").read_text().strip(); m=re.search(r"__version__\\s*=\\s*\"([^\"]+)\"", Path("src/pynescript/__about__.py").read_text()); assert v==m.group(1)=="0.7.1"'
```

## Open questions
- Whether docs seat should refresh okf/export mirrors that still say `hoox-pyne 0.7.0` in generated text (out of this card’s deploy scope).
- Whether a follow-up release/tag is wanted so GHCR `:0.7.1` exists; not started here.

## Next gate
Ready for Review → Checker verifies VERSION/`__about__` match and that no release/tag/push occurred; then Done or request commit approval.
