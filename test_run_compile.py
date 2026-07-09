import json
from backend.runtime import Runtime

script = """//@version=5
indicator("Test Compiler")
my_sma = ta.sma(close, 14)
my_ema = ta.ema(close, 14)
plot(my_sma, "SMA")
plot(my_ema, "EMA")
"""

ohlcv = []
base_price = 100
for i in range(20):
    base_price += 1
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
print("EVAL MODE:")
res_eval = r.run(script, ohlcv, mode="eval")
print(json.dumps(res_eval, indent=2))

print("\nCOMPILE MODE:")
res_comp = r.run(script, ohlcv, mode="compile")
print(json.dumps(res_comp, indent=2))
