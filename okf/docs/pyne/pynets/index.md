# docs/pyne/pynets

# Concepts

* [PyneTS CLI](cli.md) - pynets check / format / run / dump / info — Rich TTY, JSON on pipes. run calls Runtime.run, unlike Python pyne run.
* [PyneTS compile](compile.md) - JS bar-loop emit for mode compile | auto. Python object-mode analog — not Numba. auto falls back to interpret.
* [PyneTS](index.md) - TypeScript / Bun library port of PYNE — parse, unparse, Runtime.run. Python remains the semantic source of truth.
* [Install PyneTS](install.md) - Add @hoox-sh/pynets with Bun, npm, or esm.sh. CLI requires Bun. Node and browsers use the ESM bundle.
* [PyneTS missing features](missing-features.md) - Builtin and host gaps between @hoox-sh/pynets and Python pynescript.runtime. Measured 2026-09-23 on the working tree, not the published 0.2.0 tag.
* [PyneTS parity](parity.md) - How to compare @hoox-sh/pynets Runtime.run plots against Python pynescript.runtime. Python wins ties.
* [PyneTS runtime](runtime.md) - Runtime.run envelope: na is null, series lookback, call-site TA, request.security without data → na, stream and providers.
