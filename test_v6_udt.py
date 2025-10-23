#!/usr/bin/env python3
"""Quick test for v6 UDT functionality"""

from __future__ import annotations

from pynescript.ast import helper

# Test 1: Parse a simple type definition with fields
test_script_1 = """
type MyType
    int count = 0
    float price = 100.5
    string name = "default"
"""

print("Test 1: Parse simple type definition")
print("Input:")
print(test_script_1)

try:
    ast_1 = helper.parse(test_script_1)
    print("✓ Parsed successfully")
    print(f"AST: {ast_1}")
    
    # Try to unparse and check round-trip
    unparsed_1 = helper.unparse(ast_1)
    print(f"Unparsed:\n{unparsed_1}")
    
    # Try to parse the unparsed version to verify round-trip
    ast_1_rt = helper.parse(unparsed_1)
    print("✓ Round-trip successful")
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*50 + "\n")

# Test 2: Parse a type definition with varip field
test_script_2 = """
type DataPoint
    varip int value = 0
    float threshold = 50.0
"""

print("Test 2: Parse type with varip field")
print("Input:")
print(test_script_2)

try:
    ast_2 = helper.parse(test_script_2)
    print("✓ Parsed successfully")
    
    unparsed_2 = helper.unparse(ast_2)
    print(f"Unparsed:\n{unparsed_2}")
    
    # Try round-trip
    ast_2_rt = helper.parse(unparsed_2)
    print("✓ Round-trip successful")
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*50 + "\n")

# Test 3: Parse a simple script with type and method
# (Methods are typically defined at type level, but for now let's test basic parsing)
test_script_3 = """
type Calculator
    int value = 0
    int counter = 0
"""

print("Test 3: Parse type with multiple fields")
print("Input:")
print(test_script_3)

try:
    ast_3 = helper.parse(test_script_3)
    print("✓ Parsed successfully")

    unparsed_3 = helper.unparse(ast_3)
    print(f"Unparsed:\n{unparsed_3}")

    # Try round-trip
    ast_3_rt = helper.parse(unparsed_3)
    print("✓ Round-trip successful")
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*50 + "\n")

# Test 4: Parse and evaluate a simple script with type definition
test_script_4 = """
type Point
    float x = 0.0
    float y = 0.0

p = Point.new()
"""

print("Test 4: Parse and evaluate type definition with .new()")
print("Input:")
print(test_script_4)

try:
    ast_4 = helper.parse(test_script_4)
    print("✓ Parsed successfully")
    
    # Try to evaluate
    result = helper.dump(ast_4)
    print("✓ Can dump AST")
    
    unparsed_4 = helper.unparse(ast_4)
    print(f"Unparsed:\n{unparsed_4}")
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()

print("\nAll tests completed!")
