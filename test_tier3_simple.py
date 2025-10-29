#!/usr/bin/env python3
"""Simple test to validate Tier 3 function registration."""
from src.pynescript.ast.evaluator.builtins.technical import TechnicalBuiltins

# Test that all functions are registered
tech = TechnicalBuiltins()
builtin_map = tech._technical_builtin_map()

tier3_functions = [
    "ta.engulfing",
    "ta.hammer", 
    "ta.gap_detector",
    "ta.voi",
    "ta.bid_ask_imbalance",
    "ta.expected_value",
    "ta.skewness",
    "ta.kurtosis",
    "ta.parkinson",
    "ta.garman_klass"
]

print("Checking Tier 3 function registration...")
for func_name in tier3_functions:
    if func_name in builtin_map:
        print(f"✓ {func_name} registered")
    else:
        print(f"✗ {func_name} NOT registered")

print(f"\nTotal registered functions: {len(builtin_map)}")
print("Registration check complete!")
