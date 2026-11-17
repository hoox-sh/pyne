"""Positional-title parity evidence for bgcolor numeric synthesis.

Prints compile plot_titles and interpret/compile series keys for the two
blocker calls and the string-title boundary.
"""

import math
from pynescript.compiler.engine import compile_script
from pynescript.runtime import Runtime


def bars(n=4):
    out = []
    for i in range(n):
        c = 100 + 5 * math.sin(i / 3.0)
        up = i % 2 == 0
        o = c - 0.5 if up else c + 0.5
        out.append(
            {
                "time": 1_700_000_000 + i * 86400,
                "open": o,
                "high": max(o, c) + 1,
                "low": min(o, c) - 1,
                "close": c,
                "volume": 10,
            }
        )
    return out


cases = (
    ("5th-positional-title", 'bgcolor(color.red, 0, true, 10, "mytitle")'),
    ("omitted-title-4pos", "bgcolor(color.red, 0, true, 10)"),
    ("numeric-offset-5", "bgcolor(color.red, 5)"),
    ("string-title-pos2", 'bgcolor(color.red, "second")'),
)
for name, call in cases:
    src = f'//@version=5\nindicator("bg")\n{call}\nplot(close, "c")\n'
    compiled = compile_script(src, use_cache=False)
    ri = Runtime().run(src, bars(), mode="interpret")
    rc = Runtime().run(src, bars(), mode="compile")
    print(f"{name}:")
    print(f"  call           : {call}")
    print(f"  compile titles : {compiled.plot_titles}")
    print(f"  interpret keys : {sorted((ri.get('series') or {}).keys())}")
    print(f"  compile keys   : {sorted((rc.get('series') or {}).keys())}")
    print(f"  object_mode    : {compiled.object_mode}")
