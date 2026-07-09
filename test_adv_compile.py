import json
from backend.runtime import Runtime

script = """//@version=5
indicator("Test Advanced")

// Using 'var' would require special handling, but let's test reassignment
my_var = 0.0
my_var := close > open ? close : open

// History access
prev_close = close[1]
diff = close - prev_close

if diff > 0
    my_var := my_var + 1
else
    my_var := my_var - 1

plot(my_var, "My Var")
plot(diff, "Diff")
"""

ohlcv = []
base_price = 100
for i in range(10):
    base_price += 1 if i % 2 == 0 else -1
    ohlcv.append(
        {
            "time": 1000 + i,
            "open": base_price,
            "high": base_price + 2,
            "low": base_price - 2,
            "close": base_price + 1 if i % 2 == 0 else base_price - 1,
            "volume": 100,
        }
    )

r = Runtime()
print("COMPILE MODE:")
res_comp = r.run(script, ohlcv, mode="compile")
print(json.dumps(res_comp, indent=2))
