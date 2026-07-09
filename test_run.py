import requests
import json

script = """//@version=5
indicator("Test")
plot(close, "My Close")
plot(open, "My Open")
log.info("Starting execution")
if close > open
    log.warning("Bullish bar!")
"""

ohlcv = [
    {"time": 1000, "open": 100, "high": 105, "low": 95, "close": 102},
    {"time": 1001, "open": 102, "high": 103, "low": 90, "close": 98},
]

from backend.runtime import Runtime

r = Runtime()
result = r.run(script, ohlcv)
print(json.dumps(result, indent=2))
