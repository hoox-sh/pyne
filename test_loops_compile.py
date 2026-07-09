import json
from backend.runtime import Runtime

script = """//@version=5
indicator("Test Loops")

var counter = 0
for i = 1 to 5
    counter := counter + i

var while_counter = 0
while while_counter < 3
    while_counter := while_counter + 1

if not false and true
    counter := counter * 2

plot(counter, "Counter")
plot(while_counter, "While Counter")
"""

ohlcv = []
base_price = 100
for i in range(2):
    ohlcv.append(
        {
            "time": 1000 + i,
            "open": base_price,
            "high": base_price + 2,
            "low": base_price - 2,
            "close": base_price,
            "volume": 100,
        }
    )

r = Runtime()
res_comp = r.run(script, ohlcv, mode="compile")
print(json.dumps(res_comp, indent=2))
