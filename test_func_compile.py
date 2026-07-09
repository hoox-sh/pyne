import json
from backend.runtime import Runtime

script = """//@version=5
indicator("Test Function")

my_func(a, b) =>
    c = a + b
    c * 2

result = my_func(close, open)
plot(result, "Result")
"""

ohlcv = []
base_price = 100
for i in range(5):
    ohlcv.append(
        {
            "time": 1000 + i,
            "open": base_price,
            "high": base_price + 2,
            "low": base_price - 2,
            "close": base_price + 1,
            "volume": 100,
        }
    )

r = Runtime()
res_comp = r.run(script, ohlcv, mode="compile")
print(json.dumps(res_comp, indent=2))
